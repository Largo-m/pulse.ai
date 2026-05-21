import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';

final class PrdAgentRunOutput {
  const PrdAgentRunOutput({
    required this.prdMarkdown,
    this.adrs = const <AdrEntry>[],
  });

  final String prdMarkdown;
  final List<AdrEntry> adrs;
}
