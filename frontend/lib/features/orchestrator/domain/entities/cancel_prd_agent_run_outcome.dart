import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';

final class CancelPrdAgentRunOutcome {
  const CancelPrdAgentRunOutcome({
    required this.run,
    required this.cloudCancelFailed,
  });

  final PrdRunEntity run;
  final bool cloudCancelFailed;
}
