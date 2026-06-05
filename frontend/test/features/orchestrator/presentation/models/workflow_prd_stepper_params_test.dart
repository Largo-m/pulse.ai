import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_phase.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/workflow_prd_stepper_params.dart';

void main() {
  group('workflowPrdStepperParamsForPhase', () {
    test('marks PRD as current phase for draft workflow', () {
      final WorkflowPrdStepperParams params = workflowPrdStepperParamsForPhase(
        prdPhaseStatus: PrdPhaseStatus.draft,
      );

      expect(params.currentPhase, WorkflowPhase.prd);
      expect(params.completedPhases, isEmpty);
    });

    test('marks PRD completed when phase is approved', () {
      final WorkflowPrdStepperParams params = workflowPrdStepperParamsForPhase(
        prdPhaseStatus: PrdPhaseStatus.approved,
      );

      expect(params.currentPhase, WorkflowPhase.prd);
      expect(params.completedPhases, contains(WorkflowPhase.prd));
    });

    test('keeps later phases incomplete while PRD is running', () {
      final WorkflowPrdStepperParams params = workflowPrdStepperParamsForPhase(
        prdPhaseStatus: PrdPhaseStatus.running,
      );

      expect(params.currentPhase, WorkflowPhase.prd);
      expect(params.completedPhases, isEmpty);
    });
  });
}
