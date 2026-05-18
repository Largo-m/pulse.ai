import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_submit_handler.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

void main() {
  group('InitializeAgentSubmitHandler', () {
    test('handle accepts payload without throwing', () {
      expect(
        () => InitializeAgentSubmitHandler.handle(
          const InitializeAgentSubmitPayload(
            agentName: 'Bot-SRE-01',
            coreDirective: 'Monitorar alertas',
            projectId: '/Users/dev/team-repo',
            branchName: 'main',
          ),
        ),
        returnsNormally,
      );
    });
  });
}
