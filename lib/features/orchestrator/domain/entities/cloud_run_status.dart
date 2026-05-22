import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';

final class CloudRunStatus {
  const CloudRunStatus({required this.mappedPrdRunStatus});

  final PrdRunStatus mappedPrdRunStatus;
}
