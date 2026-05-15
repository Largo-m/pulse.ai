import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_state.dart';

import '../../domain/usecases/fake_recent_projects_repository.dart';

void main() {
  group('RecentProjectsCubit', () {
    late FakeRecentProjectsRepository repository;
    late ListRecentProjectsUseCase listRecentProjectsUseCase;
    late SelectActiveProjectUseCase selectActiveProjectUseCase;

    RecentProjectsCubit buildCubit({bool loadOnCreate = false}) {
      return RecentProjectsCubit(
        listRecentProjectsUseCase: listRecentProjectsUseCase,
        selectActiveProjectUseCase: selectActiveProjectUseCase,
        loadOnCreate: loadOnCreate,
      );
    }

    setUp(() {
      repository = FakeRecentProjectsRepository();
      listRecentProjectsUseCase = ListRecentProjectsUseCase(repository);
      selectActiveProjectUseCase = SelectActiveProjectUseCase(repository);
    });

    blocTest<RecentProjectsCubit, RecentProjectsState>(
      'refresh emits list and active id from repository',
      build: buildCubit,
      act: (RecentProjectsCubit cubit) async => cubit.refresh(),
      expect: () => <RecentProjectsState>[
        const RecentProjectsState(isLoading: true),
        const RecentProjectsState(isLoading: false),
      ],
    );

    blocTest<RecentProjectsCubit, RecentProjectsState>(
      'refresh emits projects and active id loaded from repository',
      build: () {
        repository.projects.add(
          LocalProjectEntity(
            id: '/Users/dev/team-repo',
            absolutePath: '/Users/dev/team-repo',
            displayName: 'team-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        );
        repository.activeProjectId = '/Users/dev/team-repo';
        return buildCubit();
      },
      act: (RecentProjectsCubit cubit) async => cubit.refresh(),
      verify: (RecentProjectsCubit cubit) {
        expect(cubit.state.projects, hasLength(1));
        expect(cubit.state.activeProjectId, '/Users/dev/team-repo');
        expect(cubit.state.isLoading, isFalse);
      },
    );

    blocTest<RecentProjectsCubit, RecentProjectsState>(
      'selectProject updates active id in state',
      build: () {
        repository.projects.add(
          LocalProjectEntity(
            id: '/Users/dev/team-repo',
            absolutePath: '/Users/dev/team-repo',
            displayName: 'team-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        );
        return buildCubit();
      },
      act: (RecentProjectsCubit cubit) async {
        await cubit.refresh();
        await cubit.selectProject('/Users/dev/team-repo');
      },
      verify: (RecentProjectsCubit cubit) {
        expect(repository.activeProjectId, '/Users/dev/team-repo');
        expect(cubit.state.activeProjectId, '/Users/dev/team-repo');
      },
    );

    blocTest<RecentProjectsCubit, RecentProjectsState>(
      'refresh reflects external repository updates',
      build: buildCubit,
      act: (RecentProjectsCubit cubit) async {
        await cubit.refresh();
        repository.projects.add(
          LocalProjectEntity(
            id: '/Users/dev/new-repo',
            absolutePath: '/Users/dev/new-repo',
            displayName: 'new-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 16, 8),
          ),
        );
        await cubit.refresh();
      },
      verify: (RecentProjectsCubit cubit) {
        expect(cubit.state.projects, hasLength(1));
        expect(cubit.state.projects.single.id, '/Users/dev/new-repo');
      },
    );

    blocTest<RecentProjectsCubit, RecentProjectsState>(
      'refresh clears active id when it is not in recent projects',
      build: () {
        repository.activeProjectId = '/Users/dev/missing';
        repository.projects.add(
          LocalProjectEntity(
            id: '/Users/dev/still-here',
            absolutePath: '/Users/dev/still-here',
            displayName: 'still-here',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        );
        return buildCubit();
      },
      act: (RecentProjectsCubit cubit) async => cubit.refresh(),
      verify: (RecentProjectsCubit cubit) {
        expect(cubit.state.activeProjectId, isNull);
        expect(repository.activeProjectId, isNull);
      },
    );
  });
}
