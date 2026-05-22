import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/workflow_techspec_gate.dart';

void main() {
  group('isTechspecWorkspaceGated', () {
    test('returns true when PRD is not approved', () {
      expect(isTechspecWorkspaceGated(PrdPhaseStatus.draft), isTrue);
      expect(isTechspecWorkspaceGated(PrdPhaseStatus.running), isTrue);
      expect(isTechspecWorkspaceGated(PrdPhaseStatus.pendingApproval), isTrue);
    });

    test('returns false when PRD is approved', () {
      expect(isTechspecWorkspaceGated(PrdPhaseStatus.approved), isFalse);
    });
  });
}
