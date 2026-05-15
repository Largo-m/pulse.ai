import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';

void main() {
  group('RecentProjectsState', () {
    test('isProjectExpanded returns true when id is in expandedProjectIds', () {
      const RecentProjectsState state = RecentProjectsState(
        expandedProjectIds: <String>['alpha', 'beta'],
      );

      expect(state.isProjectExpanded('alpha'), isTrue);
      expect(state.isProjectExpanded('gamma'), isFalse);
    });
  });
}
