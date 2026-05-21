import 'package:pulse_ai/features/orchestrator/domain/entities/prd_agent_run_output.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_completion_output_source.dart';

final class DefaultPrdRunCompletionOutputSource
    implements PrdRunCompletionOutputSource {
  const DefaultPrdRunCompletionOutputSource();

  static const PrdAgentRunOutput _placeholderOutput = PrdAgentRunOutput(
    prdMarkdown: '# PRD\n\n_Conteúdo gerado pelo agente PRD._',
  );

  @override
  Future<PrdAgentRunOutput> resolve({
    required String runId,
    required String projectId,
    required String slug,
  }) async {
    return _placeholderOutput;
  }
}
