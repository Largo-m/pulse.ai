import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

import 'fake_local_git_branches_service.dart';
import 'fake_recent_projects_repository.dart';

void main() {
  group('StartPrdRunUseCase', () {
    test('throws when context cannot be built', () async {
      final StartPrdRunUseCase useCase = StartPrdRunUseCase(
        buildPrdRunContextUseCase: BuildPrdRunContextUseCase(
          recentProjectsRepository: FakeRecentProjectsRepository(),
          listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
            service: FakeLocalGitBranchesService(),
          ),
        ),
        cursorPrdAgentService: FakeCursorPrdAgentService(),
      );

      expect(
        () => useCase(
          const PrdRunRequest(
            projectId: 'missing',
            slug: 'agent-a',
            repoPath: '/ignored',
            branchName: 'main',
            directive: 'Create PRD',
          ),
        ),
        throwsA(
          predicate<PrdRunOperationException>(
            (PrdRunOperationException error) =>
                error.failure is PrdRunFailure &&
                (error.failure as PrdRunFailure).code ==
                    PrdRunFailureCode.projectNotFound,
          ),
        ),
      );
    });

    test('starts cloud run when context is valid', () async {
      final FakeRecentProjectsRepository projectsRepository =
          FakeRecentProjectsRepository()
            ..projects.add(
              LocalProjectEntity(
                id: 'project-1',
                canonicalPath: '/Users/dev/repo',
                displayName: 'Repo',
                lastAccessedAt: DateTime.utc(2026, 5, 20),
              ),
            );
      final FakeLocalGitBranchesService gitService =
          FakeLocalGitBranchesService()
            ..resultsByPath['/Users/dev/repo'] = const LocalGitBranchesResult(
              LocalGitBranchesOutcome.success,
              branches: <String>['main'],
              headBranchName: 'main',
            );
      final StartPrdRunUseCase useCase = StartPrdRunUseCase(
        buildPrdRunContextUseCase: BuildPrdRunContextUseCase(
          recentProjectsRepository: projectsRepository,
          listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
            service: gitService,
          ),
        ),
        cursorPrdAgentService: FakeCursorPrdAgentService(),
      );

      final PrdRunEntity run = await useCase(
        const PrdRunRequest(
          projectId: 'project-1',
          slug: 'agent-a',
          repoPath: '/ignored',
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(run.cloudRunId, FakeCursorPrdAgentService.fakeCloudRunId);
    });
  });
}
