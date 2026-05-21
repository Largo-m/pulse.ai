import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';

bool isTechspecWorkspaceGated(PrdPhaseStatus prdPhaseStatus) {
  return prdPhaseStatus != PrdPhaseStatus.approved;
}
