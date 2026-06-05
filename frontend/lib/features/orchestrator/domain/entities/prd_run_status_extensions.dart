import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';

extension PrdRunStatusActive on PrdRunStatus {
  bool get acceptsStreamEvents =>
      this == PrdRunStatus.queued || this == PrdRunStatus.running;

  bool get isTerminal =>
      this == PrdRunStatus.completed ||
      this == PrdRunStatus.failed ||
      this == PrdRunStatus.cancelled;
}
