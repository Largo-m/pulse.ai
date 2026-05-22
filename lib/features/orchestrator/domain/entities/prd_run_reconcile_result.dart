import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';

enum PrdRunReconcileOutcome {
  skippedNoCloudRunId,
  skippedNoCredential,
  skippedAlreadyTerminal,
  unchanged,
  updated,
}

final class PrdRunReconcileResult {
  const PrdRunReconcileResult({required this.outcome, this.run});

  final PrdRunReconcileOutcome outcome;
  final PrdRunEntity? run;
}
