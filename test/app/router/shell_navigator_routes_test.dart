import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/app/router/shell_navigator_routes.dart';
import 'package:pulse_ai/features/orchestrator/presentation/pages/import_project_select_source_page.dart';
import 'package:pulse_ai/features/orchestrator/presentation/pages/orchestrator_empty_page.dart';

void main() {
  group('ShellNavigatorRoutes', () {
    testWidgets('builds orchestrator empty page route', (
      WidgetTester tester,
    ) async {
      final MaterialPageRoute<void> route =
          ShellNavigatorRoutes.onGenerateRoute(
                const RouteSettings(name: RoutePaths.orchestrator),
              )
              as MaterialPageRoute<void>;

      expect(route.settings.name, RoutePaths.orchestrator);

      await tester.pumpWidget(
        MaterialApp(home: Builder(builder: route.builder)),
      );

      expect(find.byType(OrchestratorEmptyPage), findsOneWidget);
    });

    testWidgets('builds import select source route', (
      WidgetTester tester,
    ) async {
      final MaterialPageRoute<void> route =
          ShellNavigatorRoutes.onGenerateRoute(
                const RouteSettings(
                  name: RoutePaths.orchestratorImportSelectSource,
                ),
              )
              as MaterialPageRoute<void>;

      expect(route.settings.name, RoutePaths.orchestratorImportSelectSource);

      await tester.pumpWidget(
        MaterialApp(home: Builder(builder: route.builder)),
      );

      expect(find.byType(ImportProjectSelectSourcePage), findsOneWidget);
    });

    test('throws for unknown route name', () {
      expect(
        () => ShellNavigatorRoutes.onGenerateRoute(
          const RouteSettings(name: '/unknown'),
        ),
        throwsArgumentError,
      );
    });
  });
}
