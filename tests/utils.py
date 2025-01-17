# Copyright ServiceNow, Inc. 2021 – 2022
# This source code is licensed under the Apache 2.0 license found in the LICENSE file
# in the root directory of this source tree.
from pathlib import Path

import numpy as np

from azimuth.config import (
    BehavioralTestingOptions,
    NeutralTokenOptions,
    TypoTestOptions,
)
from azimuth.dataset_split_manager import DatasetSplitManager, PredictionTableKey
from azimuth.modules.model_contract_task_mapping import model_contract_task_mapping
from azimuth.modules.model_performance.outcomes import OutcomesModule
from azimuth.types import (
    DatasetColumn,
    DatasetSplitName,
    ModuleOptions,
    SupportedMethod,
)
from azimuth.types.tag import (
    ALL_DATA_ACTIONS,
    ALL_PREDICTION_TAGS,
    ALL_SMART_TAGS,
    ALL_STANDARD_TAGS,
)
from azimuth.utils.ml.model_performance import compute_outcome
from azimuth.utils.project import load_dataset_from_config

_AZ_ROOT = Path(__file__).parents[1].resolve()
_CURRENT_DIR = Path(__file__).parent.resolve()
_SAMPLE_DATA_DIR = _CURRENT_DIR / "fixtures"
_SAMPLE_VOCAB_DIR = _SAMPLE_DATA_DIR / "distilbert-tokenizer-files"
_CHECKPOINT_PATH = str(_SAMPLE_VOCAB_DIR)
SIMPLE_PERTURBATION_TESTING_CONFIG = BehavioralTestingOptions(
    neutral_token=NeutralTokenOptions(suffix_list=["pls", "thanks"], prefix_list=["pls", "hello"]),
    typo=TypoTestOptions(threshold=0.005),
)

# Sentiment Analysis
PIPELINE_CFG = {
    "name": "Default Model",
    "model": {
        "class_name": "tests.test_loading_resources.load_hf_text_classif_pipeline",
        "kwargs": {"checkpoint_path": _CHECKPOINT_PATH},
    },
    "postprocessors": [{"temperature": 3}, {"threshold": 0.7}],
}
DATASET_CFG = {
    "class_name": "tests.test_loading_resources.load_sst2_dataset",
    "kwargs": {},
}

# Intent Classification
_SAMPLE_INTENT_DIR = _SAMPLE_DATA_DIR / "intent"
_SAMPLE_INTENT_TRAIN_FILE = str(_SAMPLE_INTENT_DIR / "sample_train_file.csv")
_SAMPLE_PREDICTIONS_FILEPATH_TOP1 = str(_SAMPLE_INTENT_DIR / "sample_predictions_top1.csv")
_SAMPLE_CLINC150 = str(_SAMPLE_DATA_DIR / "sample_CLINC150.json")
SAMPLE_INTENT_TRAIN_FILE_NO_INTENT = str(_SAMPLE_INTENT_DIR / "sample_train_file_wnointent.csv")
SAMPLE_PREDICTIONS_FILEPATH_TOP3 = str(_SAMPLE_INTENT_DIR / "sample_predictions_top3.csv")
DATASET_CLINC150_CFG = {
    "class_name": "tests.test_loading_resources.load_CLINC150_data",
    "kwargs": {
        "python_loader": str(_AZ_ROOT / "azimuth_shr/data/CLINC150.py"),
        "full_path": _SAMPLE_CLINC150,
    },
}
PIPELINE_GUSE_CFG = {
    "model": {
        "class_name": "tests.test_loading_resources.load_tf_model",
        "kwargs": {"checkpoint_path": _CHECKPOINT_PATH},
    }
}


def file_based_ds_from_paths(
    train=_SAMPLE_INTENT_TRAIN_FILE, test=_SAMPLE_PREDICTIONS_FILEPATH_TOP1
):
    return {
        "class_name": "tests.test_loading_resources.load_file_dataset",
        "kwargs": {
            "data_files": {
                "train": train,
                "test": test,
            },
        },
    }


def file_based_pipeline_from(ds_config):
    return {
        "class_name": "models.file_based.FileBasedModel",
        "remote": str(_AZ_ROOT / "azimuth_shr"),
        "kwargs": {
            "test_path": ds_config["kwargs"]["data_files"]["test"],
        },
    }


def save_predictions(config, ds_split_name=DatasetSplitName.eval):
    pred_mod = model_contract_task_mapping(
        dataset_split_name=ds_split_name,
        config=config,
        mod_options=ModuleOptions(
            pipeline_index=0, model_contract_method_name=SupportedMethod.Predictions
        ),
    )
    pred_res = pred_mod.compute_on_dataset_split()
    dm = pred_mod.get_dataset_split_manager()
    pred_mod.save_result(pred_res, dm)


def save_outcomes(config, ds_split_name=DatasetSplitName.eval):
    outcome_mod = OutcomesModule(
        dataset_split_name=ds_split_name,
        config=config,
        mod_options=ModuleOptions(pipeline_index=0),
    )
    outcome_res = outcome_mod.compute_on_dataset_split()
    dm = outcome_mod.get_dataset_split_manager()
    outcome_mod.save_result(outcome_res, dm)


def get_table_key(config, use_bma=False):
    return PredictionTableKey.from_pipeline_index(0, config, use_bma=use_bma)


def generate_mocked_dm(config, dataset_split_name=DatasetSplitName.eval):
    ds = load_dataset_from_config(config)[dataset_split_name]
    ds = ds.map(
        lambda x, i: {
            DatasetColumn.model_predictions: [i % 2, 1 - i % 2],
            DatasetColumn.model_confidences: [i / len(ds), 1 - i / len(ds)],
            # 0.9 simulates temperature scaling
            DatasetColumn.postprocessed_confidences: [0.9 * (i / len(ds)), 1 - 0.9 * (i / len(ds))],
            DatasetColumn.pipeline_steps: [],
            DatasetColumn.confidence_bin_idx: np.random.randint(1, 20),
        },
        with_indices=True,
    )

    base_class_names = ds.features[config.columns.label].names
    try:
        rejection_class_idx = base_class_names.index(config.rejection_class)
    except ValueError:
        rejection_class_idx = len(base_class_names)

    ds = ds.map(
        lambda x: {
            DatasetColumn.postprocessed_prediction: x[DatasetColumn.model_predictions][0]
            if x[DatasetColumn.postprocessed_confidences][0] > config.pipelines[0].threshold
            else rejection_class_idx,
        }
    )
    ds = ds.map(
        lambda x: {
            DatasetColumn.model_outcome: compute_outcome(
                x[DatasetColumn.model_predictions][0], x["label"], rejection_class_idx
            ),
            DatasetColumn.postprocessed_outcome: compute_outcome(
                x[DatasetColumn.postprocessed_prediction], x["label"], rejection_class_idx
            ),
            DatasetColumn.neighbors_train: [
                [np.random.randint(1, 1000), np.random.rand()] for i in range(0, 20)
            ],
            DatasetColumn.neighbors_eval: [
                [np.random.randint(1, 1000), np.random.rand()] for i in range(0, 20)
            ],
            DatasetColumn.word_count: np.random.randint(5, 12),
        }
    )

    dm = DatasetSplitManager(
        dataset_split_name,
        config,
        initial_tags=ALL_STANDARD_TAGS,
        initial_prediction_tags=ALL_PREDICTION_TAGS,
        dataset_split=ds,
    )
    add_tags(dm)
    faiss_features = lambda: np.random.randn(786)
    dm.add_faiss_index([faiss_features() for _ in range(dm.num_rows)])
    return dm


def add_tags(dm):
    def add_all_tags_once(all_tags):
        for idx, t in enumerate(all_tags):
            tags = {idx: {t: True}}
            dm.add_tags(tags, table_key)

    table_key = get_table_key(dm.config)
    add_all_tags_once(ALL_DATA_ACTIONS)
    add_all_tags_once(ALL_SMART_TAGS)


def get_tiny_text_config_one_ds_name(config):
    ds_name = DatasetSplitName.eval if "train" in config.dataset.kwargs else DatasetSplitName.train
    other_ds_name = (
        DatasetSplitName.train if ds_name == DatasetSplitName.eval else DatasetSplitName.eval
    )
    return ds_name, other_ds_name
