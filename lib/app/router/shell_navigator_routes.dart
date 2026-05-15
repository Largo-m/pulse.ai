import 'package:flutter/material.dart';

import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/features/orchestrator/presentation/pages/import_project_select_source_page.dart';
import 'package:pulse_ai/features/orchestrator/presentation/pages/orchestrator_empty_page.dart';

abstract final class ShellNavigatorRoutes {
  static Route<void> onGenerateRoute(RouteSettings settings) {
    switch (settings.name) {
      case RoutePaths.orchestrator:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (BuildContext context) => const OrchestratorEmptyPage(),
        );
      case RoutePaths.orchestratorImportSelectSource:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (BuildContext context) =>
              const ImportProjectSelectSourcePage(),
        );
      default:
        throw ArgumentError.value(
          settings.name,
          'name',
          'Unknown shell route: ${settings.name}',
        );
    }
  }
}
