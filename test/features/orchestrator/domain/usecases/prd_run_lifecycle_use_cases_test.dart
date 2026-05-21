import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_connection_gate.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/append_stream_event_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/cancel_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/fail_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';

import 'fake_cursor_prd_agent_service.dart';
import 'fake_local_git_branches_service.dart';
import 'fake_recent_projects_repository.dart';

void main() {
  const String projectId = '550e8400-e29b-41d4-a716-446655440000';
  const String slug = 'payments-api';
  const String repoPath = '/Users/dev/repo';

  late FakeWorkflowRepository workflowRepository;
  late FakePrdRunRepository prdRunRepository;
  late FakeArtifactRepository artifactRepository;
  late FakeRecentProjectsRepository projectsRepository;
  late FakeLocalGitBranchesService gitService;
  late FakeCursorPrdAgentServiceForLifecycle agentService;
  late BuildPrdRunContextUseCase buildContextUseCase;

  Future<void> seedWorkflow() async {
    await workflowRepository.create(
      projectId: projectId,
      slug: slug,
      branchName: 'main',
      directive: 'Build payments PRD',
    );
    projectsRepository.projects.add(
      LocalProjectEntity(
        id: projectId,
        canonicalPath: repoPath,
        displayName: 'Repo',
        lastAccessedAt: DateTime.utc(2026, 5, 20),
      ),
    );
    gitService.resultsByPath[repoPath] = const LocalGitBranchesResult(
      LocalGitBranchesOutcome.success,
      branches: <String>['main'],
      headBranchName: 'main',
    );
  }

  setUp(() {
    workflowRepository = FakeWorkflowRepository();
    prdRunRepository = FakePrdRunRepository();
    artifactRepository = FakeArtifactRepository();
    projectsRepository = FakeRecentProjectsRepository();
    gitService = FakeLocalGitBranchesService();
    agentService = FakeCursorPrdAgentServiceForLifecycle();
    buildContextUseCase = BuildPrdRunContextUseCase(
      recentProjectsRepository: projectsRepository,
      listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
        service: gitService,
      ),
    );
  });

  group('StartPrdAgentRunUseCase', () {
    test('creates queued run then running after service ack', () async {
      await seedWorkflow();

      final StartPrdAgentRunUseCase useCase = StartPrdAgentRunUseCase(
        connectionGate: PreflightPrdRunConnectionGate(
          preflight: () async => right(null),
        ),
        buildPrdRunContextUseCase: buildContextUseCase,
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        cursorPrdAgentService: agentService,
        clock: () => DateTime.utc(2026, 5, 21, 10),
      );

      final Either<Failure, PrdRunEntity> result = await useCase(
        const PrdRunRequest(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isRight(), isTrue);
      final PrdRunEntity run = result.getRight().toNullable()!;
      expect(run.status, PrdRunStatus.running);
      expect(
        run.cloudRunId,
        FakeCursorPrdAgentServiceForLifecycle.fakeCloudRunId,
      );

      final PrdRunEntity? stored = await prdRunRepository.findRunById(run.id);
      expect(stored?.status, PrdRunStatus.running);

      final WorkflowEntity? workflow = await workflowRepository.findBySlug(
        projectId: projectId,
        slug: slug,
      );
      expect(workflow?.prdPhaseStatus, PrdPhaseStatus.running);
    });

    test('returns Left when workflow does not exist', () async {
      final StartPrdAgentRunUseCase useCase = StartPrdAgentRunUseCase(
        connectionGate: PreflightPrdRunConnectionGate(
          preflight: () async => right(null),
        ),
        buildPrdRunContextUseCase: buildContextUseCase,
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        cursorPrdAgentService: agentService,
      );

      final Either<Failure, PrdRunEntity> result = await useCase(
        const PrdRunRequest(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isLeft(), isTrue);
      expect(
        (result.getLeft().toNullable() as PrdRunFailure).code,
        PrdRunFailureCode.workflowNotFound,
      );
    });

    test('marks run failed when cloud service throws', () async {
      await seedWorkflow();
      agentService.shouldFailStart = true;

      final StartPrdAgentRunUseCase useCase = StartPrdAgentRunUseCase(
        connectionGate: PreflightPrdRunConnectionGate(
          preflight: () async => right(null),
        ),
        buildPrdRunContextUseCase: buildContextUseCase,
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        cursorPrdAgentService: agentService,
      );

      final Either<Failure, PrdRunEntity> result = await useCase(
        const PrdRunRequest(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isLeft(), isTrue);
      final Either<Failure, List<PrdRunEntity>> runsResult =
          await prdRunRepository.listRunsForWorkflow(
            WorkflowKey.compose(projectId: projectId, slug: slug),
          );
      final List<PrdRunEntity> runs = runsResult.getRight().toNullable()!;
      expect(runs, hasLength(1));
      expect(runs.single.status, PrdRunStatus.failed);
    });

    test('returns Left when connection gate reports disconnected', () async {
      await seedWorkflow();

      final StartPrdAgentRunUseCase useCase = StartPrdAgentRunUseCase(
        connectionGate: PreflightPrdRunConnectionGate(
          preflight: () async => left(const CursorConnectionFailure.network()),
        ),
        buildPrdRunContextUseCase: buildContextUseCase,
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        cursorPrdAgentService: agentService,
      );

      final Either<Failure, PrdRunEntity> result = await useCase(
        const PrdRunRequest(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          branchName: 'main',
          directive: 'Create PRD',
        ),
      );

      expect(result.isLeft(), isTrue);
      expect(result.getLeft().toNullable(), isA<CursorConnectionFailure>());
    });
  });

  group('AppendStreamEventUseCase', () {
    test('stores three events with sequences 1, 2, 3 for same runId', () async {
      await seedWorkflow();
      final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
          .createRun(
            workflowKey: WorkflowKey.compose(projectId: projectId, slug: slug),
            status: PrdRunStatus.running,
          );
      final String runId = runResult.getRight().toNullable()!.id;

      final AppendStreamEventUseCase useCase = AppendStreamEventUseCase(
        prdRunRepository: prdRunRepository,
        artifactRepository: artifactRepository,
      );

      final DateTime timestamp = DateTime.utc(2026, 5, 21, 11);
      for (int index = 1; index <= 3; index++) {
        final Either<Failure, StreamEventEntity> result = await useCase(
          runId: runId,
          projectId: projectId,
          slug: slug,
          event: PrdStreamEvent(
            runId: 'cloud-run',
            eventType: 'assistant',
            sequence: index,
            timestamp: timestamp.add(Duration(milliseconds: index)),
            payloadSummary: 'line $index',
          ),
        );
        expect(result.isRight(), isTrue);
      }

      final Either<Failure, List<StreamEventEntity>> listed =
          await prdRunRepository.listStreamEvents(runId);
      final List<StreamEventEntity> events = listed.getRight().toNullable()!;
      expect(events.map((StreamEventEntity event) => event.sequence), <int>[
        1,
        2,
        3,
      ]);
      expect(artifactRepository.streamJsonlEvents, hasLength(3));
    });

    test('rejects append when run is cancelled', () async {
      await seedWorkflow();
      final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
          .createRun(
            workflowKey: WorkflowKey.compose(projectId: projectId, slug: slug),
            status: PrdRunStatus.cancelled,
          );
      final String runId = runResult.getRight().toNullable()!.id;

      final AppendStreamEventUseCase useCase = AppendStreamEventUseCase(
        prdRunRepository: prdRunRepository,
      );

      final Either<Failure, StreamEventEntity> result = await useCase(
        runId: runId,
        projectId: projectId,
        slug: slug,
        event: PrdStreamEvent(
          runId: 'cloud-run',
          eventType: 'assistant',
          sequence: 1,
          timestamp: DateTime.utc(2026, 5, 21),
        ),
      );

      expect(result.isLeft(), isTrue);
      expect(
        (result.getLeft().toNullable() as PrdRunFailure).code,
        PrdRunFailureCode.runNotActive,
      );
    });
  });

  group('CancelPrdAgentRunUseCase', () {
    test(
      'in-flight run becomes cancelled and cloud cancel is invoked',
      () async {
        await seedWorkflow();
        final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
            .createRun(
              workflowKey: WorkflowKey.compose(
                projectId: projectId,
                slug: slug,
              ),
              status: PrdRunStatus.running,
              cloudRunId: FakeCursorPrdAgentServiceForLifecycle.fakeCloudRunId,
            );
        final String runId = runResult.getRight().toNullable()!.id;

        final CancelPrdAgentRunUseCase useCase = CancelPrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          cursorPrdAgentService: agentService,
          clock: () => DateTime.utc(2026, 5, 21, 12),
        );

        final Either<Failure, PrdRunEntity> result = await useCase(
          runId: runId,
          projectId: projectId,
          slug: slug,
        );

        expect(result.isRight(), isTrue);
        expect(result.getRight().toNullable()!.status, PrdRunStatus.cancelled);
        expect(agentService.cancelRunCallCount, 1);
        expect(
          agentService.lastCancelledCloudRunId,
          FakeCursorPrdAgentServiceForLifecycle.fakeCloudRunId,
        );

        final AppendStreamEventUseCase appendUseCase = AppendStreamEventUseCase(
          prdRunRepository: prdRunRepository,
        );
        final Either<Failure, StreamEventEntity> appendResult =
            await appendUseCase(
              runId: runId,
              projectId: projectId,
              slug: slug,
              event: PrdStreamEvent(
                runId: 'cloud-run',
                eventType: 'assistant',
                sequence: 1,
                timestamp: DateTime.utc(2026, 5, 21, 12, 1),
              ),
            );
        expect(appendResult.isLeft(), isTrue);
      },
    );
  });

  group('CompletePrdAgentRunUseCase', () {
    test(
      'writes prd markdown, sets pendingApproval, and marks run completed',
      () async {
        await seedWorkflow();
        final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
            .createRun(
              workflowKey: WorkflowKey.compose(
                projectId: projectId,
                slug: slug,
              ),
              status: PrdRunStatus.running,
            );
        final String runId = runResult.getRight().toNullable()!.id;

        final CompletePrdAgentRunUseCase useCase = CompletePrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          artifactRepository: artifactRepository,
          clock: () => DateTime.utc(2026, 5, 21, 13),
        );

        final Either<Failure, PrdRunEntity> result = await useCase(
          runId: runId,
          projectId: projectId,
          slug: slug,
          output: FakeCursorPrdAgentServiceForLifecycle.sampleCompletionOutput,
        );

        expect(result.isRight(), isTrue);
        expect(result.getRight().toNullable()!.status, PrdRunStatus.completed);

        final WorkflowEntity? workflow = await workflowRepository.findBySlug(
          projectId: projectId,
          slug: slug,
        );
        expect(workflow?.prdPhaseStatus, PrdPhaseStatus.pendingApproval);

        final approval = await prdRunRepository.findApproval(
          WorkflowKey.compose(projectId: projectId, slug: slug),
        );
        expect(approval?.status, PrdApprovalStatus.pendingApproval);
        expect(approval?.sourceRunId, runId);

        final Either<Failure, String> markdown = await artifactRepository
            .readPrdMarkdown(projectId: projectId, slug: slug);
        expect(
          markdown.getRight().toNullable(),
          FakeCursorPrdAgentServiceForLifecycle.samplePrdMarkdown,
        );
      },
    );
  });

  group('FailPrdAgentRunUseCase', () {
    test('maps failure to failed without pending approval metadata', () async {
      await seedWorkflow();
      final Either<Failure, PrdRunEntity> runResult = await prdRunRepository
          .createRun(
            workflowKey: WorkflowKey.compose(projectId: projectId, slug: slug),
            status: PrdRunStatus.running,
          );
      final String runId = runResult.getRight().toNullable()!.id;

      final FailPrdAgentRunUseCase useCase = FailPrdAgentRunUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        clock: () => DateTime.utc(2026, 5, 21, 14),
      );

      final Either<Failure, PrdRunEntity> result = await useCase(
        runId: runId,
        projectId: projectId,
        slug: slug,
      );

      expect(result.isRight(), isTrue);
      expect(result.getRight().toNullable()!.status, PrdRunStatus.failed);

      final approval = await prdRunRepository.findApproval('$projectId::$slug');
      expect(approval, isNull);

      final WorkflowEntity? workflow = await workflowRepository.findBySlug(
        projectId: projectId,
        slug: slug,
      );
      expect(workflow?.prdPhaseStatus, PrdPhaseStatus.draft);
    });
  });

  group('PrdStreamBufferPolicy', () {
    test('caps in-memory stream buffer for presentation', () {
      expect(PrdStreamBufferPolicy.maxInMemoryEvents, 200);
    });
  });
}
