# Copyright ServiceNow, Inc. 2021 – 2022
# This source code is licensed under the Apache 2.0 license found in the LICENSE file
# in the root directory of this source tree.
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

import numpy as np
from datasets import Dataset
from tqdm import tqdm

from azimuth.config import ModelContractConfig
from azimuth.dataset_split_manager import DatasetSplitManager
from azimuth.modules.base_classes import AggregationModule, FilterableModule
from azimuth.modules.model_performance.outcomes import OutcomesModule
from azimuth.types import DatasetColumn, ModuleOptions
from azimuth.types.model_performance import (
    OutcomeCountPerFilter,
    OutcomeCountPerFilterResponse,
    OutcomeCountPerFilterValue,
    OutcomeCountPerThresholdResponse,
    OutcomeCountPerThresholdValue,
)
from azimuth.types.outcomes import ALL_OUTCOMES, OutcomeName
from azimuth.types.tag import (
    ALL_DATA_ACTION_FILTERS,
    SMART_TAGS_FAMILY_MAPPING,
    SmartTag,
)
from azimuth.utils.dataset_operations import get_outcomes_from_ds
from azimuth.utils.ml.model_performance import (
    sorted_by_utterance_count,
    sorted_by_utterance_count_with_last,
)
from azimuth.utils.project import postprocessing_editable
from azimuth.utils.validation import assert_is_list


class OutcomeCountPerFilterModule(FilterableModule[ModelContractConfig]):
    """Computes the outcome count for each filter."""

    def get_outcome_count_per_class(
        self, dm: DatasetSplitManager, ds: Dataset, dataset_column: str
    ) -> List[OutcomeCountPerFilterValue]:
        """Get outcome count for a specific class name, either in label or prediction.

        Args:
            dm: DatasetSplitManager
            ds: Dataset Split.
            dataset_column: Column on which to compute the outcome count (prediction or label)

        Returns:
            Outcome count per class name.

        """
        outcome_count_per_class: Dict[Tuple[str, OutcomeName], int] = defaultdict(int)

        for utterance_class, outcome in zip(
            ds[dataset_column], get_outcomes_from_ds(ds, self.mod_options.without_postprocessing)
        ):
            outcome_count_per_class[(dm.get_class_names()[utterance_class], outcome)] += 1

        return sorted_by_utterance_count_with_last(
            self.get_outcome_count(outcome_count_per_class, dm.get_class_names()),
            dm.rejection_class_idx,
        )

    def get_outcome_count_per_tag(
        self, dm: DatasetSplitManager, ds: Dataset, filters: List[str]
    ) -> List[OutcomeCountPerFilterValue]:
        """Get outcome count for a list of tag filter options.

        Args:
            dm: DatasetSplitManager.
            ds: Dataset Split.
            filters: Tag filter options, assuming the last item (-1) is NO_ACTION/NO_SMART_TAGS.

        Returns:
            Outcome count per tag.

        """
        outcome_count_per_tag: Dict[Tuple[str, OutcomeName], int] = defaultdict(int)

        all_tags = dm.get_tags(
            indices=assert_is_list(ds[DatasetColumn.row_idx]), table_key=self._get_table_key()
        )
        for utterance_tags, outcome in zip(
            all_tags.values(), get_outcomes_from_ds(ds, self.mod_options.without_postprocessing)
        ):
            no_tag = True
            for filter_, tagged in utterance_tags.items():
                if tagged and filter_ in filters[:-1]:
                    outcome_count_per_tag[(filter_, outcome)] += 1
                    no_tag = False
            if no_tag:
                outcome_count_per_tag[(filters[-1], outcome)] += 1

        return sorted_by_utterance_count_with_last(
            self.get_outcome_count(outcome_count_per_tag, filters), -1
        )

    def get_outcome_count_per_outcome(self, ds: Dataset) -> List[OutcomeCountPerFilterValue]:
        """Compute outcome count per outcome.

        Args:
            ds: Dataset Split.

        Returns:
            List of Outcome Count for each outcome.

        """
        outcome_count = defaultdict(
            int, Counter(get_outcomes_from_ds(ds, self.mod_options.without_postprocessing))
        )
        empty_outcome_count = {outcome: 0 for outcome in OutcomeName}

        metrics = [
            OutcomeCountPerFilterValue(
                outcome_count={**empty_outcome_count, outcome: outcome_count[outcome]},
                utterance_count=outcome_count[outcome],
                filter_value=outcome,
            )
            for outcome in OutcomeName
        ]
        return sorted_by_utterance_count(metrics)

    @classmethod
    def get_outcome_count(
        cls,
        outcome_count_per_filter: Dict[Tuple[str, OutcomeName], int],
        filters: List[str],
    ) -> List[OutcomeCountPerFilterValue]:
        """Compute outcome count and total amount for a given set of filters.

        Args:
            outcome_count_per_filter: Outcome count per filter.
            filters: List of filters.

        Returns:
            List of outcome counts for the set of filters.

        """
        return [
            OutcomeCountPerFilterValue(
                outcome_count={
                    outcome: outcome_count_per_filter[(filter_value, outcome)]
                    for outcome in ALL_OUTCOMES
                },
                utterance_count=sum(
                    outcome_count_per_filter[(filter_value, outcome)] for outcome in ALL_OUTCOMES
                ),
                filter_value=filter_value,
            )
            for filter_value in filters
        ]

    def compute_on_dataset_split(self) -> List[OutcomeCountPerFilterResponse]:  # type: ignore
        dm = self.get_dataset_split_manager()
        ds = self.get_dataset_split()

        return [
            OutcomeCountPerFilterResponse(
                count_per_filter=OutcomeCountPerFilter(
                    label=self.get_outcome_count_per_class(dm, ds, dm.config.columns.label),
                    prediction=self.get_outcome_count_per_class(
                        dm, ds, DatasetColumn.postprocessed_prediction
                    ),
                    data_action=self.get_outcome_count_per_tag(dm, ds, ALL_DATA_ACTION_FILTERS),
                    outcome=self.get_outcome_count_per_outcome(ds),
                    **{
                        family.value: self.get_outcome_count_per_tag(
                            dm, ds, tags + [SmartTag.no_smart_tag]
                        )
                        for family, tags in SMART_TAGS_FAMILY_MAPPING.items()
                    },
                ),
                utterance_count=len(ds),
            )
        ]


class OutcomeCountPerThresholdModule(AggregationModule[ModelContractConfig]):
    """Compute the outcome count per threshold."""

    required_mod_options = {"pipeline_index"}
    optional_mod_options = {"x_ticks_count"}

    def compute_on_dataset_split(self) -> List[OutcomeCountPerThresholdResponse]:  # type: ignore
        if not postprocessing_editable(self.config, self.mod_options.pipeline_index):
            raise ValueError("Postprocessing is not editable")

        x_ticks_count = self.mod_options.x_ticks_count
        ths = np.linspace(0, 1, x_ticks_count)
        result = []
        for th in tqdm(
            ths,
            desc=f"{self.task_name} on {self.dataset_split_name} set "
            f"for pipeline {self.mod_options.pipeline_index}",
        ):
            outcomes_mod = OutcomesModule(
                dataset_split_name=self.dataset_split_name,
                config=self.config,
                mod_options=ModuleOptions(
                    # Convert to float instead of numpy.float64
                    threshold=float(th),
                    pipeline_index=self.mod_options.pipeline_index,
                ),
            )
            outcomes = outcomes_mod.compute_on_dataset_split()
            postprocessed_outcomes = [outcome.postprocessed_outcome for outcome in outcomes]
            result.append(
                OutcomeCountPerThresholdValue(
                    threshold=th,
                    outcome_count=Counter(postprocessed_outcomes),
                )
            )
        return [
            OutcomeCountPerThresholdResponse(
                outcome_count_per_threshold=result,
                confidence_threshold=self.get_threshold(),
                utterance_count=len(self.get_dataset_split()),
            )
        ]
