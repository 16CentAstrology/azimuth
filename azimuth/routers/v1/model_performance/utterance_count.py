# Copyright ServiceNow, Inc. 2021 – 2022
# This source code is licensed under the Apache 2.0 license found in the LICENSE file
# in the root directory of this source tree.
from collections import Counter
from typing import Dict, List

from fastapi import APIRouter, Depends

from azimuth.app import get_config, get_dataset_split_manager
from azimuth.config import AzimuthConfig
from azimuth.dataset_split_manager import DatasetSplitManager
from azimuth.types import NamedDatasetFilters
from azimuth.types.model_performance import (
    UtteranceCountPerFilter,
    UtteranceCountPerFilterResponse,
    UtteranceCountPerFilterValue,
)
from azimuth.types.tag import (
    ALL_DATA_ACTIONS,
    DATASET_SMART_TAG_FAMILIES,
    SMART_TAGS_FAMILY_MAPPING,
    SmartTag,
    SmartTagFamily,
)
from azimuth.utils.conversion import merge_counters
from azimuth.utils.dataset_operations import filter_dataset_split
from azimuth.utils.ml.model_performance import sorted_by_utterance_count_with_last
from azimuth.utils.routers import build_named_dataset_filters

router = APIRouter()

TAGS = ["Utterance Count v1"]


def get_default_counter(value_list) -> Counter:
    return Counter(**{value: 0 for value in value_list})


def counter_to_count_per_filter_value(counter: Counter) -> List[UtteranceCountPerFilterValue]:
    return [
        UtteranceCountPerFilterValue(filter_value=filter_value, utterance_count=utt_count)
        for filter_value, utt_count in counter.items()
    ]


@router.get(
    "/per_filter",
    summary="Get count for each filter.",
    description="Get count for each filter based on the current filtering.",
    tags=TAGS,
    response_model=UtteranceCountPerFilterResponse,
)
def get_count_per_filter(
    named_filters: NamedDatasetFilters = Depends(build_named_dataset_filters),
    dataset_split_manager: DatasetSplitManager = Depends(get_dataset_split_manager),
    config: AzimuthConfig = Depends(get_config),
) -> UtteranceCountPerFilterResponse:
    full_ds = dataset_split_manager.get_dataset_split_with_class_names()
    ds = filter_dataset_split(full_ds, named_filters, config)
    class_names = dataset_split_manager.get_class_names()

    label_counter = merge_counters(
        get_default_counter(class_names), Counter(ds[config.columns.label])
    )
    smart_tag_counter: Dict[SmartTagFamily, Counter] = {
        tag_family: Counter(
            **{
                SmartTag.no_smart_tag.value: sum(
                    ds.to_pandas()[SMART_TAGS_FAMILY_MAPPING[tag_family]]  # type: ignore[index]
                    .to_numpy()
                    .sum(1)
                    == 0
                )
            },
            **{
                t: sum(ds[t]) if t in ds.column_names else 0
                for t in SMART_TAGS_FAMILY_MAPPING[tag_family]
            },
        )
        for tag_family in DATASET_SMART_TAG_FAMILIES
    }
    data_action_counter: Counter = Counter(**{t: sum(ds[t]) for t in ALL_DATA_ACTIONS})

    return UtteranceCountPerFilterResponse(
        count_per_filter=UtteranceCountPerFilter(
            label=sorted_by_utterance_count_with_last(
                counter_to_count_per_filter_value(label_counter),
                dataset_split_manager.rejection_class_idx,
            ),
            **{
                family.value: sorted_by_utterance_count_with_last(
                    counter_to_count_per_filter_value(counters), 0
                )
                for family, counters in smart_tag_counter.items()
            },
            data_action=sorted_by_utterance_count_with_last(
                counter_to_count_per_filter_value(data_action_counter),
                -1,
            ),
        ),
        utterance_count=len(ds),
    )
