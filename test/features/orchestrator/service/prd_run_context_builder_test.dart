import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/service/prd_run_context_builder.dart';

import '../domain/usecases/fake_local_git_branches_service.dart';
import '../domain/usecases/fake_recent_projects_repository.dart';

void main() {
  group('PrdRunContextBuilder', () {
    late FakeRecentProjectsRepository projectsRepository;
    late FakeLocalGitBranchesService gitService;
    late PrdRunContextBuilder builder;

    setUp(() {
      projectsRepository = FakeRecentProjectsRepository();
      gitService = FakeLocalGitBranchesService();
      builder = PrdRunContextBuilder(
        recentProjectsRepository: projectsRepository,
        listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
          service: gitService,
        ),
      );
    });

    test('returns projectNotFound when UUID is missing', () async {
      final Either<Failure, PrdRunContext> result = await builder.build(
        const PrdRunRequest(
          projectId: 'missing-project',
          slug: 'agent-a',
          repoPath: '/ignored',
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isLeft(), isTrue);
      result.fold((Failure failure) {
        expect(failure, isA<PrdRunFailure>());
        expect(
          (failure as PrdRunFailure).code,
          PrdRunFailureCode.projectNotFound,
        );
      }, (_) => fail('expected left'));
    });

    test('builds context from canonical path and validates branch', () async {
      projectsRepository.projects.add(
        LocalProjectEntity(
          id: 'project-1',
          canonicalPath: '/Users/dev/repo',
          displayName: 'Repo',
          lastAccessedAt: DateTime.utc(2026, 5, 20),
          macosSecurityScopedBookmark: 'bookmark',
        ),
      );
      gitService.resultsByPath['/Users/dev/repo'] =
          const LocalGitBranchesResult(
            LocalGitBranchesOutcome.success,
            branches: <String>['main', 'develop'],
            headBranchName: 'main',
          );

      final Either<Failure, PrdRunContext> result = await builder.build(
        const PrdRunRequest(
          projectId: 'project-1',
          slug: 'agent-a',
          repoPath: '/should-not-be-used',
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (PrdRunContext context) {
        expect(context.canonicalPath, '/Users/dev/repo');
        expect(context.composedPrompt, contains('/Users/dev/repo'));
        expect(context.composedPrompt, contains('agent-a'));
        expect(context.composedPrompt, isNot(contains('/should-not-be-used')));
      });
      expect(gitService.lastAbsolutePath, '/Users/dev/repo');
      expect(gitService.lastMacosSecurityScopedBookmark, 'bookmark');
    });

    test(
      'returns branchInvalid when branch is absent from repository',
      () async {
        projectsRepository.projects.add(
          LocalProjectEntity(
            id: 'project-1',
            canonicalPath: '/Users/dev/repo',
            displayName: 'Repo',
            lastAccessedAt: DateTime.utc(2026, 5, 20),
          ),
        );
        gitService.resultsByPath['/Users/dev/repo'] =
            const LocalGitBranchesResult(
              LocalGitBranchesOutcome.success,
              branches: <String>['develop'],
              headBranchName: 'develop',
            );

        final Either<Failure, PrdRunContext> result = await builder.build(
          const PrdRunRequest(
            projectId: 'project-1',
            slug: 'agent-a',
            repoPath: '/ignored',
            branchName: 'main',
            directive: 'Create PRD',
          ),
        );

        expect(result.isLeft(), isTrue);
        result.fold((Failure failure) {
          expect(
            (failure as PrdRunFailure).code,
            PrdRunFailureCode.branchInvalid,
          );
        }, (_) => fail('expected left'));
      },
    );

    test('includes feedback and supersedesRunId in composed prompt', () async {
      projectsRepository.projects.add(
        LocalProjectEntity(
          id: 'project-1',
          canonicalPath: '/Users/dev/repo',
          displayName: 'Repo',
          lastAccessedAt: DateTime.utc(2026, 5, 20),
        ),
      );
      gitService.resultsByPath['/Users/dev/repo'] =
          const LocalGitBranchesResult(
            LocalGitBranchesOutcome.success,
            branches: <String>['main'],
            headBranchName: 'main',
          );

      final Either<Failure, PrdRunContext> result = await builder.build(
        const PrdRunRequest(
          projectId: 'project-1',
          slug: 'agent-a',
          repoPath: '/ignored',
          branchName: 'main',
          directive: 'Create PRD',
          feedback: 'Add more detail',
          supersedesRunId: 'run-prev',
        ),
      );

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (PrdRunContext context) {
        expect(context.composedPrompt, contains('Feedback:'));
        expect(context.composedPrompt, contains('Supersedes run:'));
        expect(context.feedback, 'Add more detail');
        expect(context.supersedesRunId, 'run-prev');
      });
    });

    test('returns gitContextUnavailable when git lookup fails', () async {
      projectsRepository.projects.add(
        LocalProjectEntity(
          id: 'project-1',
          canonicalPath: '/Users/dev/repo',
          displayName: 'Repo',
          lastAccessedAt: DateTime.utc(2026, 5, 20),
        ),
      );
      gitService.resultsByPath['/Users/dev/repo'] =
          const LocalGitBranchesResult(
            LocalGitBranchesOutcome.notGitRepository,
          );

      final Either<Failure, PrdRunContext> result = await builder.build(
        const PrdRunRequest(
          projectId: 'project-1',
          slug: 'agent-a',
          repoPath: '/ignored',
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isLeft(), isTrue);
      result.fold((Failure failure) {
        expect(
          (failure as PrdRunFailure).code,
          PrdRunFailureCode.gitContextUnavailable,
        );
      }, (_) => fail('expected left'));
    });
  });
}
