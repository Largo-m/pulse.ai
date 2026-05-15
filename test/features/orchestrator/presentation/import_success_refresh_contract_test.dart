import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';

import '../domain/usecases/fake_local_directory_picker_service.dart';
import '../domain/usecases/fake_recent_projects_repository.dart';

void main() {
  group('Import success refresh contract', () {
    test(
      'importLocal success followed by refresh exposes project in RecentProjectsCubit',
      () async {
        final FakeRecentProjectsRepository repository =
            FakeRecentProjectsRepository();
        final FakeLocalDirectoryPickerService picker =
            FakeLocalDirectoryPickerService()
              ..nextResult = const DirectoryPickResult(
                DirectoryPickOutcome.success,
                absolutePath: '/Users/dev/team-repo',
              );

        final ImportLocalProjectUseCase importLocalProjectUseCase =
            ImportLocalProjectUseCase(
              repository: repository,
              pickerService: picker,
              clock: () => DateTime.utc(2026, 5, 15, 12),
            );
        final ListRecentProjectsUseCase listRecentProjectsUseCase =
            ListRecentProjectsUseCase(repository);
        final SelectActiveProjectUseCase selectActiveProjectUseCase =
            SelectActiveProjectUseCase(repository);

        final ImportFlowCubit importFlowCubit = ImportFlowCubit(
          importLocalProjectUseCase: importLocalProjectUseCase,
        );
        final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
          listRecentProjectsUseCase: listRecentProjectsUseCase,
          selectActiveProjectUseCase: selectActiveProjectUseCase,
          loadOnCreate: false,
        );
        addTearDown(importFlowCubit.close);
        addTearDown(recentProjectsCubit.close);

        await importFlowCubit.importLocal();

        expect(importFlowCubit.state.status, ImportFlowStatus.success);
        expect(repository.upsertCallCount, 1);

        await recentProjectsCubit.refresh();

        expect(recentProjectsCubit.state.projects, hasLength(1));
        expect(
          recentProjectsCubit.state.activeProjectId,
          '/Users/dev/team-repo',
        );
        expect(
          recentProjectsCubit.state.projects.first.displayName,
          'team-repo',
        );
      },
    );
  });
}
