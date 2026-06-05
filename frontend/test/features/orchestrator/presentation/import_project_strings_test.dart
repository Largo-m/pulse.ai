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

    test('exposes non-empty PT-BR copy for import failure messages', () {
      expect(ImportProjectStrings.importLocalFailureMessage, isNotEmpty);
      expect(
        ImportProjectStrings.importLocalFailureMessage,
        contains('importar'),
      );
      expect(
        ImportProjectStrings.importLocalPermissionFailureMessage,
        isNotEmpty,
      );
      expect(
        ImportProjectStrings.importLocalPermissionFailureMessage,
        contains('Permissão'),
      );
    });

    test('import failure strings are not English placeholders', () {
      expect(
        ImportProjectStrings.importLocalFailureMessage,
        isNot(equals('Could not import local project')),
      );
      expect(
        ImportProjectStrings.importLocalPermissionFailureMessage,
        isNot(equals('Permission denied')),
      );
    });
  });
}
