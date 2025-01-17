import { Box, Button, Typography } from "@mui/material";
import noData from "assets/void.svg";
import PerturbationTestingPreview from "components/Analysis/PerturbationTestingPreview";
import PreviewCard from "components/Analysis/PreviewCard";
import WarningsPreview from "components/Analysis/WarningsPreview";
import ClassOverlapTable from "components/ClassOverlapTable";
import Description from "components/Description";
import Telescope from "components/Icons/Telescope";
import Loading from "components/Loading";
import PerformanceAnalysis from "components/Metrics/PerformanceAnalysis";
import SmartTagsTable from "components/SmartTagsTable";
import ThresholdPlot from "components/ThresholdPlot";
import WithDatasetSplitNameState from "components/WithDatasetSplitNameState";
import useQueryState from "hooks/useQueryState";
import React from "react";
import { Link, useParams } from "react-router-dom";
import { getConfigEndpoint, getDatasetInfoEndpoint } from "services/api";
import { DATASET_SPLIT_NAMES, UNKNOWN_ERROR } from "utils/const";
import { isPipelineSelected } from "utils/helpers";
import { performanceAnalysisDescription } from "./PerformanceAnalysis";
import { behavioralTestingDescription } from "./PerturbationTestingSummary";
import { smartTagsDescription } from "./SmartTags";
import { postprocessingDescription } from "./Threshold";

const DEFAULT_PREVIEW_CONTENT_HEIGHT = 502;

const Dashboard = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const { pipeline, searchString } = useQueryState();

  const { data: config } = getConfigEndpoint.useQuery({ jobId });

  const {
    data: datasetInfo,
    error,
    isFetching,
  } = getDatasetInfoEndpoint.useQuery({ jobId });

  if (isFetching) {
    return <Loading />;
  } else if (error || datasetInfo === undefined) {
    return (
      <Box alignItems="center" display="grid" justifyItems="center">
        <img src={noData} width="50%" alt="no dataset info" />
        <Typography>{error?.message || UNKNOWN_ERROR}</Typography>
      </Box>
    );
  }

  const firstAvailableDatasetSplit = DATASET_SPLIT_NAMES.find(
    (datasetSplitName) => datasetInfo.availableDatasetSplits[datasetSplitName]
  )!;

  return (
    <Box display="flex" flexDirection="column" gap={2}>
      <Box
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        paddingX={4}
        paddingY={1}
      >
        <Box display="flex" flexDirection="column">
          <Typography variant="h2">Dashboard</Typography>
          <Description
            text="Explore the analyses of your datasets and pipelines."
            link="user-guide/"
          />
        </Box>
        <Button
          color="secondary"
          variant="contained"
          component={Link}
          to={`/${jobId}/dataset_splits/${firstAvailableDatasetSplit}/prediction_overview${searchString}`}
          sx={{ gap: 1 }}
        >
          <Telescope fontSize="large" />
          Go to exploration space
        </Button>
      </Box>
      <PreviewCard
        title="Dataset Warnings"
        to={`/${jobId}/dataset_warnings${searchString}`}
        description={
          <Description
            text="Investigate issues related to class size, class imbalance, or dataset shift between your training and evaluation sets."
            link="user-guide/dataset-warnings/"
          />
        }
      >
        <Box height={DEFAULT_PREVIEW_CONTENT_HEIGHT}>
          <WarningsPreview jobId={jobId} />
        </Box>
      </PreviewCard>
      {datasetInfo.availableDatasetSplits.train &&
        datasetInfo.similarityAvailable && (
          <PreviewCard
            title="Class Overlap"
            to={`/${jobId}/dataset_splits/train/class_overlap${searchString}`}
            description={
              <Description
                text="Assess semantic overlap between class pairs and compare to pipeline confusion."
                link="user-guide/class-overlap/"
              />
            }
          >
            <ClassOverlapTable
              jobId={jobId}
              pipeline={pipeline}
              availableDatasetSplits={datasetInfo.availableDatasetSplits}
            />
          </PreviewCard>
        )}
      {isPipelineSelected(pipeline) && (
        <WithDatasetSplitNameState
          defaultDatasetSplitName={firstAvailableDatasetSplit}
          render={(datasetSplitName, setDatasetSplitName) => (
            <PreviewCard
              title="Pipeline Metrics by Data Subpopulation"
              to={`/${jobId}/dataset_splits/${datasetSplitName}/pipeline_metrics${searchString}`}
              linkButtonText={
                config?.pipelines && config.pipelines.length > 1
                  ? "Compare pipelines"
                  : undefined
              }
              description={performanceAnalysisDescription}
            >
              <PerformanceAnalysis
                jobId={jobId}
                pipeline={pipeline}
                availableDatasetSplits={datasetInfo.availableDatasetSplits}
                datasetSplitName={datasetSplitName}
                setDatasetSplitName={setDatasetSplitName}
              />
            </PreviewCard>
          )}
        />
      )}
      {isPipelineSelected(pipeline) && (
        <WithDatasetSplitNameState
          defaultDatasetSplitName={firstAvailableDatasetSplit}
          render={(datasetSplitName, setDatasetSplitName) => (
            <PreviewCard
              title="Smart Tag Analysis"
              to={`/${jobId}/dataset_splits/${datasetSplitName}/smart_tags${searchString}`}
              description={smartTagsDescription}
            >
              <Box
                display="flex"
                flexDirection="column" // Important for the inner Box to overflow correctly
                maxHeight={DEFAULT_PREVIEW_CONTENT_HEIGHT}
              >
                <SmartTagsTable
                  jobId={jobId}
                  pipeline={pipeline}
                  availableDatasetSplits={datasetInfo.availableDatasetSplits}
                  datasetSplitName={datasetSplitName}
                  setDatasetSplitName={setDatasetSplitName}
                />
              </Box>
            </PreviewCard>
          )}
        />
      )}
      {isPipelineSelected(pipeline) &&
        datasetInfo.perturbationTestingAvailable && (
          <PreviewCard
            title="Behavioral Testing"
            to={`/${jobId}/behavioral_testing_summary${searchString}`}
            description={behavioralTestingDescription}
          >
            <Box height={DEFAULT_PREVIEW_CONTENT_HEIGHT}>
              <PerturbationTestingPreview
                jobId={jobId}
                pipeline={pipeline}
                availableDatasetSplits={datasetInfo.availableDatasetSplits}
              />
            </Box>
          </PreviewCard>
        )}
      {isPipelineSelected(pipeline) &&
        datasetInfo.availableDatasetSplits.eval &&
        datasetInfo.postprocessingEditable?.[pipeline.pipelineIndex] && (
          <PreviewCard
            title="Post-processing Analysis"
            to={`/${jobId}/thresholds${searchString}`}
            description={postprocessingDescription}
          >
            <Box height={DEFAULT_PREVIEW_CONTENT_HEIGHT}>
              <ThresholdPlot jobId={jobId} pipeline={pipeline} />
            </Box>
          </PreviewCard>
        )}
    </Box>
  );
};

export default React.memo(Dashboard);
