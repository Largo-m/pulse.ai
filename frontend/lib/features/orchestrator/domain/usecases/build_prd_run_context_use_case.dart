import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_machine_name.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_origin_remote_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';

final class BuildPrdRunContextUseCase {
  BuildPrdRunContextUseCase({
    required RecentProjectsRepository recentProjectsRepository,
    required ListLocalGitBranchesUseCase listLocalGitBranchesUseCase,
    required LocalGitOriginRemoteService localGitOriginRemoteService,
  }) : _recentProjectsRepository = recentProjectsRepository,
       _listLocalGitBranchesUseCase = listLocalGitBranchesUseCase,
       _localGitOriginRemoteService = localGitOriginRemoteService;

  final RecentProjectsRepository _recentProjectsRepository;
  final ListLocalGitBranchesUseCase _listLocalGitBranchesUseCase;
  final LocalGitOriginRemoteService _localGitOriginRemoteService;

  Future<Either<Failure, PrdRunContext>> call(PrdRunRequest request) async {
    final List<LocalProjectEntity> projects = await _recentProjectsRepository
        .listRecent();
    LocalProjectEntity? project;
    for (final LocalProjectEntity candidate in projects) {
      if (candidate.id == request.projectId) {
        project = candidate;
        break;
      }
    }

    if (project == null) {
      return left(const PrdRunFailure.projectNotFound());
    }

    final LocalGitBranchesResult branchResult =
        await _listLocalGitBranchesUseCase(
          absolutePath: project.canonicalPath,
          macosSecurityScopedBookmark: project.macosSecurityScopedBookmark,
        );

    switch (branchResult.outcome) {
      case LocalGitBranchesOutcome.success:
        if (!branchResult.branches.contains(request.branchName)) {
          return left(const PrdRunFailure.branchInvalid());
        }
      case LocalGitBranchesOutcome.notGitRepository:
      case LocalGitBranchesOutcome.permissionDenied:
      case LocalGitBranchesOutcome.failure:
        return left(const PrdRunFailure.gitContextUnavailable());
    }

    final LocalGitOriginRemoteResult remoteResult =
        await _localGitOriginRemoteService.resolveOriginRemoteUrl(
          project.canonicalPath,
          macosSecurityScopedBookmark: project.macosSecurityScopedBookmark,
        );

    final String? repositoryUrl =
        remoteResult.outcome == LocalGitOriginRemoteOutcome.success
        ? remoteResult.githubHttpsUrl
        : null;

    return right(
      PrdRunContext(
        projectId: request.projectId,
        slug: request.slug,
        canonicalPath: project.canonicalPath,
        machineName: PrdRunMachineName.forProject(request.projectId),
        repositoryUrl: repositoryUrl,
        branchName: request.branchName,
        composedPrompt: _composePrompt(context: project, request: request),
        macosSecurityScopedBookmark: project.macosSecurityScopedBookmark,
        supersedesRunId: request.supersedesRunId,
        feedback: request.feedback,
      ),
    );
  }

  String _composePrompt({
    required LocalProjectEntity context,
    required PrdRunRequest request,
  }) {
    final StringBuffer buffer = StringBuffer()
      ..writeln('Pulse PRD specialist run')
      ..writeln('Project: ${request.projectId}')
      ..writeln('Workflow slug: ${request.slug}')
      ..writeln(
        'My Machines worker: ${PrdRunMachineName.forProject(request.projectId)}',
      )
      ..writeln(
        'Local workspace (edit files only here): ${context.canonicalPath}',
      )
      ..writeln('Git branch (local checkout): ${request.branchName}')
      ..writeln(
        'Constraint: apply all code and file changes on this machine under the '
        'local workspace path. Do not modify remote GitHub repositories or cloud clones.',
      )
      ..writeln('Directive:')
      ..writeln(request.directive.trim());

    if (request.feedback != null && request.feedback!.trim().isNotEmpty) {
      buffer
        ..writeln()
        ..writeln('Feedback:')
        ..writeln(request.feedback!.trim());
    }

    if (request.supersedesRunId != null &&
        request.supersedesRunId!.trim().isNotEmpty) {
      buffer
        ..writeln()
        ..writeln('Supersedes run: ${request.supersedesRunId!.trim()}');
    }

    return buffer.toString().trim();
  }
}
