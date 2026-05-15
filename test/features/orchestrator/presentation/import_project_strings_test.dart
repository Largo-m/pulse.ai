import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/import_project_strings.dart';

void main() {
  group('ImportProjectStrings', () {
    test('exposes non-empty PT-BR copy for page header', () {
      expect(ImportProjectStrings.pageTitle, isNotEmpty);
      expect(ImportProjectStrings.pageSubtitle, isNotEmpty);
      expect(ImportProjectStrings.pageTitle, contains('Importar'));
    });

    test('exposes non-empty labels for local and remote source cards', () {
      expect(ImportProjectStrings.selectLocal, isNotEmpty);
      expect(ImportProjectStrings.selectRemote, isNotEmpty);
      expect(ImportProjectStrings.localTitle, isNot(equals('Local Workspace')));
    });

    test('exposes feature bullets for both import paths', () {
      expect(ImportProjectStrings.localFeatureZeroLatency, isNotEmpty);
      expect(ImportProjectStrings.remoteFeatureBranchManagement, isNotEmpty);
    });
  });
}
