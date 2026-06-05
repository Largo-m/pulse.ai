import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/app/router/route_paths.dart';

void main() {
  group('RoutePaths', () {
    test('orchestrator import path uses kebab-case segment', () {
      expect(
        RoutePaths.orchestratorImportSelectSource,
        '/orchestrator/import/select-source',
      );
    });

    test('orchestrator paths are distinct', () {
      expect(
        RoutePaths.orchestrator,
        isNot(equals(RoutePaths.orchestratorImportSelectSource)),
      );
    });
  });
}
