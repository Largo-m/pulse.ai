import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/recent_project_tree_agent_ui_model.dart';

void main() {
  group('RecentProjectTreeAgentUiModel', () {
    test('defaults isRunning to false', () {
      const RecentProjectTreeAgentUiModel agent = RecentProjectTreeAgentUiModel(
        displayName: 'ScraperAgent',
        isActive: true,
      );

      expect(agent.isRunning, isFalse);
    });
  });
}
