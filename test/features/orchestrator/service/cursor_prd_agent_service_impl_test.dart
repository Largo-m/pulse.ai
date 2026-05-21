import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_prd_agent_service_impl.dart';
import 'package:pulse_ai/features/orchestrator/service/prd_run_context_builder.dart';
import 'package:pulse_ai/features/orchestrator/service/transient_http_retry.dart';
import 'package:uuid/uuid.dart';

import '../domain/service/fakes/fake_cursor_credential_store_service.dart';
import '../domain/usecases/fake_local_git_branches_service.dart';
import '../domain/usecases/fake_recent_projects_repository.dart';
import 'fakes/fake_cursor_cloud_agent_http_client.dart';

void main() {
  group('CursorPrdAgentServiceImpl', () {
    late FakeCursorCredentialStoreService credentialStore;
    late FakeRecentProjectsRepository projectsRepository;
    late FakeLocalGitBranchesService gitService;
    late FakeCursorCloudAgentHttpClient httpClient;
    late CursorPrdAgentServiceImpl service;

    setUp(() {
      credentialStore = FakeCursorCredentialStoreService()
        ..storedCredential = 'cursor-api-key';
      projectsRepository = FakeRecentProjectsRepository()
        ..projects.add(
          LocalProjectEntity(
            id: 'project-1',
            canonicalPath: '/Users/dev/repo',
            displayName: 'Repo',
            lastAccessedAt: DateTime.utc(2026, 5, 20),
          ),
        );
      gitService = FakeLocalGitBranchesService()
        ..resultsByPath['/Users/dev/repo'] = const LocalGitBranchesResult(
          LocalGitBranchesOutcome.success,
          branches: <String>['main'],
          headBranchName: 'main',
        );
      httpClient = FakeCursorCloudAgentHttpClient();
      service = CursorPrdAgentServiceImpl(
        credentialStore: credentialStore,
        contextBuilder: PrdRunContextBuilder(
          recentProjectsRepository: projectsRepository,
          listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
            service: gitService,
          ),
        ),
        httpClient: httpClient,
        uuid: const Uuid(),
      );
    });

    test(
      'startRun with valid request returns PrdRunEntity with cloudRunId',
      () async {
        httpClient.nextPostResponse = const CursorHttpResponse(
          statusCode: 200,
          body: '{"agent":{"id":"bc-agent-1"},"run":{"id":"run-agent-1"}}',
        );

        final PrdRunEntity run = await service.startRun(
          const PrdRunRequest(
            projectId: 'project-1',
            slug: 'agent-a',
            repoPath: '/ignored',
            branchName: 'main',
            directive: 'Create PRD',
          ),
        );

        expect(run.cloudRunId, isNotEmpty);
        expect(run.cloudRunId, contains('bc-agent-1'));
        expect(run.cloudRunId, contains('run-agent-1'));
        expect(gitService.listLocalBranchesCallCount, 1);
        expect(httpClient.postPaths.single, '/v1/agents');
      },
    );

    test('watchRun emits three ordered events from SSE fixture', () async {
      httpClient
              .sseLinesByPath['/v1/agents/bc-agent-1/runs/run-agent-1/stream'] =
          File('test/fixtures/cursor/run_stream.sse').readAsLinesSync();

      final List<PrdStreamEvent> events = await service
          .watchRun('bc-agent-1::run-agent-1')
          .toList();

      expect(events.length, 3);
      expect(
        events.map((PrdStreamEvent event) => event.sequence).toList(),
        <int>[1, 2, 3],
      );
    });

    test('cancelRun invokes cancel endpoint once', () async {
      httpClient
              .postResponsesByPath['/v1/agents/bc-agent-1/runs/run-agent-1/cancel'] =
          const CursorHttpResponse(
            statusCode: 200,
            body: '{"id":"run-agent-1"}',
          );

      await service.cancelRun('bc-agent-1::run-agent-1');

      expect(httpClient.postCallCount, 1);
      expect(
        httpClient.postPaths.single,
        '/v1/agents/bc-agent-1/runs/run-agent-1/cancel',
      );
    });

    test('5xx response triggers bounded retry policy', () async {
      final CursorPrdAgentServiceImpl retryService = CursorPrdAgentServiceImpl(
        credentialStore: credentialStore,
        contextBuilder: PrdRunContextBuilder(
          recentProjectsRepository: projectsRepository,
          listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
            service: gitService,
          ),
        ),
        httpClient: httpClient,
        retryPolicy: const TransientHttpRetry(maxAttempts: 3),
        uuid: const Uuid(),
      );

      httpClient.postResponseQueue.addAll(<CursorHttpResponse>[
        const CursorHttpResponse(statusCode: 503, body: '{}'),
        const CursorHttpResponse(statusCode: 503, body: '{}'),
        const CursorHttpResponse(
          statusCode: 200,
          body: '{"agent":{"id":"bc-agent-1"},"run":{"id":"run-agent-1"}}',
        ),
      ]);

      await retryService.startRun(
        const PrdRunRequest(
          projectId: 'project-1',
          slug: 'agent-a',
          repoPath: '/ignored',
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(httpClient.postCallCount, 3);
    });

    test('preflight maps 401 to unauthorized failure', () async {
      httpClient.nextGetResponse = const CursorHttpResponse(
        statusCode: 401,
        body: '{}',
      );

      final result = await service.preflight();

      expect(result.isLeft(), isTrue);
      result.fold((failure) {
        expect(failure, isA<CursorConnectionFailure>());
        expect(
          (failure as CursorConnectionFailure).code,
          CursorConnectionFailureCode.unauthorized,
        );
      }, (_) => fail('expected left'));
    });

    test('watchRun throws when cloudRunId cannot be decoded', () async {
      expect(
        () => service.watchRun('invalid-cloud-run-id').first,
        throwsA(isA<PrdRunOperationException>()),
      );
    });

    test('missing project UUID in builder throws projectNotFound', () async {
      expect(
        () => service.startRun(
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
      expect(httpClient.postCallCount, 0);
    });
  });
}
