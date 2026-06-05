import 'package:pulse_ai/features/orchestrator/domain/entities/prd_agent_run_output.dart';

abstract interface class PrdRunCompletionOutputSource {
  Future<PrdAgentRunOutput> resolve({
    required String runId,
    required String projectId,
    required String slug,
  });
}
