import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

void main() {
  group('OrchestratorStrings', () {
    test('exposes non-empty PT-BR copy for primary empty state', () {
      expect(OrchestratorStrings.emptyStateTitle, isNotEmpty);
      expect(OrchestratorStrings.emptyStateSubtitle, isNotEmpty);
      expect(OrchestratorStrings.emptyStateTitle, contains('Bem-vindo'));
    });

    test('exposes non-empty CTA labels for local and remote flows', () {
      expect(OrchestratorStrings.localProjectButton, isNotEmpty);
      expect(OrchestratorStrings.remoteProjectButton, isNotEmpty);
      expect(
        OrchestratorStrings.localProjectTitle,
        isNot(equals('Open Local Project')),
      );
    });

    test('comingSoonMessage is defined for placeholder feedback', () {
      expect(OrchestratorStrings.comingSoonMessage, isNotEmpty);
    });

    test('exposes non-empty PT-BR copy for recent projects sidebar', () {
      expect(OrchestratorStrings.recentProjectsSectionTitle, isNotEmpty);
      expect(
        OrchestratorStrings.recentProjectsSectionTitle,
        contains('Projetos recentes'),
      );
      expect(OrchestratorStrings.recentProjectListTileTooltip, isNotEmpty);
      expect(OrchestratorStrings.recentProjectSelectSemantics, isNotEmpty);
      expect(OrchestratorStrings.recentProjectActiveSemantics, isNotEmpty);
    });

    test('recent projects sidebar strings are not English placeholders', () {
      expect(
        OrchestratorStrings.recentProjectsSectionTitle,
        isNot(equals('Recent Projects')),
      );
      expect(
        OrchestratorStrings.recentProjectListTileTooltip,
        isNot(equals('Select project')),
      );
    });
  });
}
