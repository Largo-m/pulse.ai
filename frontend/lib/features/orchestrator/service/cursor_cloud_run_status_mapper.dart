import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';

final class CursorCloudRunStatusMapper {
  const CursorCloudRunStatusMapper();

  PrdRunStatus? mapCloudStatus(String rawStatus) {
    switch (rawStatus.trim().toUpperCase()) {
      case 'FINISHED':
        return PrdRunStatus.completed;
      case 'ERROR':
      case 'EXPIRED':
        return PrdRunStatus.failed;
      case 'CANCELLED':
        return PrdRunStatus.cancelled;
      case 'RUNNING':
      case 'CREATING':
        return PrdRunStatus.running;
      default:
        return null;
    }
  }
}
