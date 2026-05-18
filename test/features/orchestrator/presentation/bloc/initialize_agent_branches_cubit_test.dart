import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';

import '../../domain/usecases/fake_local_git_branches_service.dart';

void main() {
  group('InitializeAgentBranchesState', () {
    test('copyWith updates fields and supports clearing nullable values', () {
      const InitializeAgentBranchesState original =
          InitializeAgentBranchesState(
            status: BranchLoadStatus.loaded,
            branches: <String>['main'],
            selectedBranch: 'main',
            activePath: '/Users/dev/repo',
            loadGeneration: 2,
          );

      final InitializeAgentBranchesState cleared = original.copyWith(
        clearSelectedBranch: true,
        clearActivePath: true,
        status: BranchLoadStatus.loading,
        branches: <String>['develop'],
        loadGeneration: 3,
      );

      expect(cleared.status, BranchLoadStatus.loading);
      expect(cleared.branches, <String>['develop']);
      expect(cleared.selectedBranch, isNull);
      expect(cleared.activePath, isNull);
      expect(cleared.loadGeneration, 3);
    });

    test('equality compares branches list content', () {
      const InitializeAgentBranchesState left = InitializeAgentBranchesState(
        branches: <String>['main', 'develop'],
      );
      const InitializeAgentBranchesState right = InitializeAgentBranchesState(
        branches: <String>['main', 'develop'],
      );
      const InitializeAgentBranchesState different =
          InitializeAgentBranchesState(branches: <String>['main']);

      expect(left, right);
      expect(left, isNot(different));
      expect(left.hashCode, right.hashCode);
    });
  });

  group('InitializeAgentBranchesCubit', () {
    late FakeLocalGitBranchesService fakeService;
    late ListLocalGitBranchesUseCase useCase;

    InitializeAgentBranchesCubit buildCubit() {
      return InitializeAgentBranchesCubit(listLocalGitBranchesUseCase: useCase);
    }

    setUp(() {
      fakeService = FakeLocalGitBranchesService();
      useCase = ListLocalGitBranchesUseCase(service: fakeService);
    });

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'loadForProject emits loading then loaded with head pre-selected',
      build: buildCubit,
      act: (InitializeAgentBranchesCubit cubit) async {
        fakeService.nextResult = const LocalGitBranchesResult(
          LocalGitBranchesOutcome.success,
          branches: <String>['main', 'feature/x'],
          headBranchName: 'main',
        );
        await cubit.loadForProject(absolutePath: '/Users/dev/repo-a');
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loading,
          activePath: '/Users/dev/repo-a',
          loadGeneration: 1,
        ),
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loaded,
          branches: <String>['main', 'feature/x'],
          selectedBranch: 'main',
          activePath: '/Users/dev/repo-a',
          loadGeneration: 1,
        ),
      ],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'loadForProject emits notGitRepository without selected branch',
      build: buildCubit,
      act: (InitializeAgentBranchesCubit cubit) async {
        fakeService.nextResult = const LocalGitBranchesResult(
          LocalGitBranchesOutcome.notGitRepository,
        );
        await cubit.loadForProject(absolutePath: '/Users/dev/not-git');
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loading,
          activePath: '/Users/dev/not-git',
          loadGeneration: 1,
        ),
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.notGitRepository,
          activePath: '/Users/dev/not-git',
          loadGeneration: 1,
        ),
      ],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'loadForProject emits permissionDenied',
      build: buildCubit,
      act: (InitializeAgentBranchesCubit cubit) async {
        fakeService.nextResult = const LocalGitBranchesResult(
          LocalGitBranchesOutcome.permissionDenied,
        );
        await cubit.loadForProject(
          absolutePath: '/Users/dev/repo-sandbox',
          macosSecurityScopedBookmark: 'bookmark-data',
        );
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loading,
          activePath: '/Users/dev/repo-sandbox',
          loadGeneration: 1,
        ),
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.permissionDenied,
          activePath: '/Users/dev/repo-sandbox',
          loadGeneration: 1,
        ),
      ],
      verify: (_) {
        expect(fakeService.lastMacosSecurityScopedBookmark, 'bookmark-data');
      },
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'loadForProject emits failure',
      build: buildCubit,
      act: (InitializeAgentBranchesCubit cubit) async {
        fakeService.nextResult = const LocalGitBranchesResult(
          LocalGitBranchesOutcome.failure,
          debugMessage: 'permission denied',
        );
        await cubit.loadForProject(absolutePath: '/Users/dev/repo-b');
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loading,
          activePath: '/Users/dev/repo-b',
          loadGeneration: 1,
        ),
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.failure,
          activePath: '/Users/dev/repo-b',
          loadGeneration: 1,
        ),
      ],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'selectBranch is ignored when status is not loaded',
      build: buildCubit,
      seed: () => const InitializeAgentBranchesState(
        status: BranchLoadStatus.loading,
        activePath: '/Users/dev/repo-a',
        loadGeneration: 1,
      ),
      act: (InitializeAgentBranchesCubit cubit) {
        cubit.selectBranch('feature/x');
      },
      expect: () => <InitializeAgentBranchesState>[],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'selectBranch updates selectedBranch while loaded',
      build: buildCubit,
      seed: () => const InitializeAgentBranchesState(
        status: BranchLoadStatus.loaded,
        branches: <String>['main', 'feature/x'],
        selectedBranch: 'main',
        activePath: '/Users/dev/repo-a',
        loadGeneration: 1,
      ),
      act: (InitializeAgentBranchesCubit cubit) {
        cubit.selectBranch('feature/x');
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loaded,
          branches: <String>['main', 'feature/x'],
          selectedBranch: 'feature/x',
          activePath: '/Users/dev/repo-a',
          loadGeneration: 1,
        ),
      ],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'rapid loadForProject calls ignore stale response',
      build: buildCubit,
      act: (InitializeAgentBranchesCubit cubit) async {
        fakeService.delaysByPath['/Users/dev/slow'] = const Duration(
          milliseconds: 50,
        );
        fakeService.resultsByPath['/Users/dev/slow'] =
            const LocalGitBranchesResult(
              LocalGitBranchesOutcome.success,
              branches: <String>['stale'],
              headBranchName: 'stale',
            );
        fakeService.resultsByPath['/Users/dev/fast'] =
            const LocalGitBranchesResult(
              LocalGitBranchesOutcome.success,
              branches: <String>['fast'],
              headBranchName: 'fast',
            );

        final Future<void> slowLoad = cubit.loadForProject(
          absolutePath: '/Users/dev/slow',
        );
        await cubit.loadForProject(absolutePath: '/Users/dev/fast');
        await slowLoad;
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loading,
          activePath: '/Users/dev/slow',
          loadGeneration: 1,
        ),
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loading,
          activePath: '/Users/dev/fast',
          loadGeneration: 2,
        ),
        const InitializeAgentBranchesState(
          status: BranchLoadStatus.loaded,
          branches: <String>['fast'],
          selectedBranch: 'fast',
          activePath: '/Users/dev/fast',
          loadGeneration: 2,
        ),
      ],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'reset returns to initial state',
      build: buildCubit,
      seed: () => const InitializeAgentBranchesState(
        status: BranchLoadStatus.loaded,
        branches: <String>['main'],
        selectedBranch: 'main',
        activePath: '/Users/dev/repo-a',
        loadGeneration: 3,
      ),
      act: (InitializeAgentBranchesCubit cubit) {
        cubit.reset();
      },
      expect: () => <InitializeAgentBranchesState>[
        const InitializeAgentBranchesState(),
      ],
    );

    blocTest<InitializeAgentBranchesCubit, InitializeAgentBranchesState>(
      'detached HEAD emits loaded with null selectedBranch',
      build: buildCubit,
      act: (InitializeAgentBranchesCubit cubit) async {
        fakeService.nextResult = const LocalGitBranchesResult(
          LocalGitBranchesOutcome.success,
          branches: <String>['main', 'develop'],
          headBranchName: null,
        );
        await cubit.loadForProject(absolutePath: '/Users/dev/detached');
      },
      verify: (InitializeAgentBranchesCubit cubit) {
        expect(cubit.state.status, BranchLoadStatus.loaded);
        expect(cubit.state.branches, isNotEmpty);
        expect(cubit.state.selectedBranch, isNull);
      },
    );
  });
}
