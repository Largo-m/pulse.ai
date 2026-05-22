import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/utils/workflow_progress_calculator.dart';

void main() {
  group('workflowProgressPercent', () {
    test('returns 0 when phase is not started', () {
      expect(
        workflowProgressPercent(
          phaseStatus: PrdWorkflowPhaseUiStatus.notStarted,
          streamLineCount: 0,
        ),
        0,
      );
    });

    test('returns capped running progress from stream line count', () {
      expect(
        workflowProgressPercent(
          phaseStatus: PrdWorkflowPhaseUiStatus.running,
          streamLineCount: 0,
        ),
        12,
      );
      expect(
        workflowProgressPercent(
          phaseStatus: PrdWorkflowPhaseUiStatus.running,
          streamLineCount: 12,
        ),
        95,
      );
    });

    test('returns 100 when pending approval', () {
      expect(
        workflowProgressPercent(
          phaseStatus: PrdWorkflowPhaseUiStatus.pendingApproval,
          streamLineCount: 3,
        ),
        100,
      );
    });
  });

  group('workflowProgressLabel', () {
    test('formats percent in PT-BR', () {
      expect(workflowProgressLabel(68), '68% concluído');
    });
  });

  group('workflowTechspecCompletionLabel', () {
    test('formats completion label in uppercase style', () {
      expect(workflowTechspecCompletionLabel(45), '45% DE CONCLUSÃO');
    });
  });
}
