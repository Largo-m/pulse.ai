import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_phase.dart';

final class WorkflowPrdStepperParams {
  const WorkflowPrdStepperParams({
    required this.currentPhase,
    required this.completedPhases,
  });

  final WorkflowPhase currentPhase;
  final Set<WorkflowPhase> completedPhases;
}

WorkflowPrdStepperParams workflowPrdStepperParamsForPhase({
  required PrdPhaseStatus prdPhaseStatus,
}) {
  final Set<WorkflowPhase> completedPhases =
      prdPhaseStatus == PrdPhaseStatus.approved
      ? const <WorkflowPhase>{WorkflowPhase.prd}
      : const <WorkflowPhase>{};

  return WorkflowPrdStepperParams(
    currentPhase: WorkflowPhase.prd,
    completedPhases: completedPhases,
  );
}
