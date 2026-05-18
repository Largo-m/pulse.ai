import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/app/router/route_paths.dart';
import 'package:pulse_ai/app/router/shell_navigator_routes.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/pages/import_project_select_source_page.dart';
import 'package:pulse_ai/features/orchestrator/presentation/pages/orchestrator_page.dart';

import '../../features/orchestrator/domain/usecases/fake_local_directory_picker_service.dart';
import '../../features/orchestrator/domain/usecases/fake_recent_projects_repository.dart';

void main() {
  group('ShellNavigatorRoutes', () {
    testWidgets('builds orchestrator page route', (WidgetTester tester) async {
      final MaterialPageRoute<void> route =
          ShellNavigatorRoutes.onGenerateRoute(
                const RouteSettings(name: RoutePaths.orchestrator),
              )
              as MaterialPageRoute<void>;

      expect(route.settings.name, RoutePaths.orchestrator);

      final FakeRecentProjectsRepository repository =
          FakeRecentProjectsRepository();
      final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
        listRecentProjectsUseCase: ListRecentProjectsUseCase(repository),
        selectActiveProjectUseCase: SelectActiveProjectUseCase(repository),
        loadOnCreate: false,
      );
      final ImportFlowCubit importFlowCubit = ImportFlowCubit(
        importLocalProjectUseCase: ImportLocalProjectUseCase(
          repository: repository,
          pickerService: FakeLocalDirectoryPickerService(),
        ),
      );
      final OrchestratorMainContentCubit orchestratorMainContentCubit =
          OrchestratorMainContentCubit();
      addTearDown(recentProjectsCubit.close);
      addTearDown(importFlowCubit.close);
      addTearDown(orchestratorMainContentCubit.close);

      await tester.pumpWidget(
        MaterialApp(
          home: MultiBlocProvider(
            providers: <BlocProvider<dynamic>>[
              BlocProvider<RecentProjectsCubit>.value(
                value: recentProjectsCubit,
              ),
              BlocProvider<ImportFlowCubit>.value(value: importFlowCubit),
              BlocProvider<OrchestratorMainContentCubit>.value(
                value: orchestratorMainContentCubit,
              ),
            ],
            child: Builder(builder: route.builder),
          ),
        ),
      );

      expect(find.byType(OrchestratorPage), findsOneWidget);
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

      final FakeRecentProjectsRepository repository =
          FakeRecentProjectsRepository();
      final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
        listRecentProjectsUseCase: ListRecentProjectsUseCase(repository),
        selectActiveProjectUseCase: SelectActiveProjectUseCase(repository),
        loadOnCreate: false,
      );
      final ImportFlowCubit importFlowCubit = ImportFlowCubit(
        importLocalProjectUseCase: ImportLocalProjectUseCase(
          repository: repository,
          pickerService: FakeLocalDirectoryPickerService(),
        ),
      );
      addTearDown(recentProjectsCubit.close);
      addTearDown(importFlowCubit.close);

      await tester.pumpWidget(
        MaterialApp(
          home: MultiBlocProvider(
            providers: <BlocProvider<dynamic>>[
              BlocProvider<RecentProjectsCubit>.value(
                value: recentProjectsCubit,
              ),
              BlocProvider<ImportFlowCubit>.value(value: importFlowCubit),
            ],
            child: Builder(builder: route.builder),
          ),
        ),
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
