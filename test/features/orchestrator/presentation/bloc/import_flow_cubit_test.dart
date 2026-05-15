import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';

import '../../domain/usecases/fake_local_directory_picker_service.dart';
import '../../domain/usecases/fake_recent_projects_repository.dart';

void main() {
  group('ImportFlowCubit', () {
    late FakeRecentProjectsRepository repository;
    late FakeLocalDirectoryPickerService picker;
    late ImportLocalProjectUseCase importLocalProjectUseCase;

    ImportFlowCubit buildCubit() {
      return ImportFlowCubit(
        importLocalProjectUseCase: importLocalProjectUseCase,
      );
    }

    setUp(() {
      repository = FakeRecentProjectsRepository();
      picker = FakeLocalDirectoryPickerService();
      importLocalProjectUseCase = ImportLocalProjectUseCase(
        repository: repository,
        pickerService: picker,
        clock: () => DateTime.utc(2026, 5, 15, 12),
      );
    });

    blocTest<ImportFlowCubit, ImportFlowState>(
      'importLocal emits loading then success when use case succeeds',
      build: buildCubit,
      act: (ImportFlowCubit cubit) async {
        picker.nextResult = const DirectoryPickResult(
          DirectoryPickOutcome.success,
          absolutePath: '/Users/dev/team-repo',
        );
        await cubit.importLocal();
      },
      expect: () => <ImportFlowState>[
        const ImportFlowState(status: ImportFlowStatus.loading),
        ImportFlowState(
          status: ImportFlowStatus.success,
          project: LocalProjectEntity(
            id: '/Users/dev/team-repo',
            absolutePath: '/Users/dev/team-repo',
            displayName: 'team-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        ),
      ],
      verify: (ImportFlowCubit cubit) {
        expect(repository.activeProjectId, '/Users/dev/team-repo');
      },
    );

    blocTest<ImportFlowCubit, ImportFlowState>(
      'importLocal emits cancelled without failure when picker is cancelled',
      build: buildCubit,
      act: (ImportFlowCubit cubit) async {
        picker.nextResult = const DirectoryPickResult(
          DirectoryPickOutcome.cancelled,
        );
        await cubit.importLocal();
      },
      expect: () => <ImportFlowState>[
        const ImportFlowState(status: ImportFlowStatus.loading),
        const ImportFlowState(status: ImportFlowStatus.cancelled),
      ],
      verify: (ImportFlowCubit cubit) {
        expect(cubit.state.status, isNot(ImportFlowStatus.failure));
        expect(repository.upsertCallCount, 0);
      },
    );

    blocTest<ImportFlowCubit, ImportFlowState>(
      'importLocal emits failure with message when use case fails',
      build: buildCubit,
      act: (ImportFlowCubit cubit) async {
        picker.nextResult = const DirectoryPickResult(
          DirectoryPickOutcome.failure,
          failureMessage: 'permission denied',
        );
        await cubit.importLocal();
      },
      expect: () => <ImportFlowState>[
        const ImportFlowState(status: ImportFlowStatus.loading),
        const ImportFlowState(
          status: ImportFlowStatus.failure,
          failureMessage: 'permission denied',
        ),
      ],
    );
  });
}
