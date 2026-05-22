import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflow_adrs_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_adr_list_load_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';

void main() {
  const String projectId = '550e8400-e29b-41d4-a716-446655440000';
  const String slugA = 'payments-api';
  const String slugB = 'billing-api';

  late FakeArtifactRepository artifactRepository;
  late ListWorkflowAdrsUseCase useCase;

  PrdAdrListCubit buildCubit() {
    return PrdAdrListCubit(listWorkflowAdrsUseCase: useCase);
  }

  setUp(() {
    artifactRepository = FakeArtifactRepository();
    useCase = ListWorkflowAdrsUseCase(artifactRepository);
  });

  group('PrdAdrListCubit', () {
    blocTest<PrdAdrListCubit, PrdAdrListState>(
      'loadAdrs emits ready with entries from use case',
      build: buildCubit,
      act: (PrdAdrListCubit cubit) async {
        final String key = WorkflowKey.compose(
          projectId: projectId,
          slug: slugA,
        );
        artifactRepository.adrsByKey[key] = <AdrEntry>[
          const AdrEntry(
            fileName: 'adr-001.md',
            sequenceNumber: 1,
            markdown: '# ADR 1',
          ),
        ];
        cubit.bindContext(projectId: projectId, slug: slugA);
        await cubit.loadAdrs();
      },
      verify: (PrdAdrListCubit cubit) {
        expect(cubit.state.loadStatus, PrdAdrListLoadStatus.ready);
        expect(cubit.state.entries, hasLength(1));
        expect(cubit.state.entries.first.fileName, 'adr-001.md');
        expect(cubit.state.failureMessageKey, isNull);
      },
    );

    blocTest<PrdAdrListCubit, PrdAdrListState>(
      'loadAdrs with missing storage uses missingArtifact key',
      build: () {
        return PrdAdrListCubit(
          listWorkflowAdrsUseCase: ListWorkflowAdrsUseCase(
            _NotFoundArtifactRepository(),
          ),
        );
      },
      act: (PrdAdrListCubit cubit) async {
        cubit.bindContext(projectId: projectId, slug: slugA);
        await cubit.loadAdrs();
      },
      verify: (PrdAdrListCubit cubit) {
        expect(cubit.state.loadStatus, PrdAdrListLoadStatus.error);
        expect(
          cubit.state.failureMessageKey,
          PrdArtifactFailureMessageKeys.missingArtifact,
        );
        expect(cubit.state.entries, isEmpty);
      },
    );
  });

  group('ListWorkflowAdrsUseCase workflow isolation', () {
    test(
      'two workflows with distinct ADRs do not cross-bind by slug',
      () async {
        final String keyA = WorkflowKey.compose(
          projectId: projectId,
          slug: slugA,
        );
        final String keyB = WorkflowKey.compose(
          projectId: projectId,
          slug: slugB,
        );
        artifactRepository.adrsByKey[keyA] = <AdrEntry>[
          const AdrEntry(
            fileName: 'adr-a.md',
            sequenceNumber: 1,
            markdown: 'A',
          ),
        ];
        artifactRepository.adrsByKey[keyB] = <AdrEntry>[
          const AdrEntry(
            fileName: 'adr-b.md',
            sequenceNumber: 1,
            markdown: 'B',
          ),
        ];

        final Either<Failure, List<AdrEntry>> resultA = await useCase(
          projectId: projectId,
          slug: slugA,
        );
        final Either<Failure, List<AdrEntry>> resultB = await useCase(
          projectId: projectId,
          slug: slugB,
        );

        resultA.fold((_) => fail('expected right'), (List<AdrEntry> adrs) {
          expect(adrs.single.fileName, 'adr-a.md');
        });
        resultB.fold((_) => fail('expected right'), (List<AdrEntry> adrs) {
          expect(adrs.single.fileName, 'adr-b.md');
        });
      },
    );
  });
}

final class _NotFoundArtifactRepository implements ArtifactRepository {
  @override
  Future<Either<Failure, String>> readPrdMarkdown({
    required String projectId,
    required String slug,
  }) async {
    return left(const ArtifactPersistenceFailure.notFound());
  }

  @override
  Future<Either<Failure, void>> writePrdMarkdown({
    required String projectId,
    required String slug,
    required String markdown,
    required PrdArtifactMetadata metadata,
  }) async {
    return left(const ArtifactPersistenceFailure.ioError());
  }

  @override
  Future<Either<Failure, List<AdrEntry>>> listAdrs({
    required String projectId,
    required String slug,
  }) async {
    return left(const ArtifactPersistenceFailure.notFound());
  }

  @override
  Future<Either<Failure, void>> writeAdrMarkdown({
    required String projectId,
    required String slug,
    required AdrEntry entry,
  }) async {
    return left(const ArtifactPersistenceFailure.ioError());
  }

  @override
  Future<Either<Failure, void>> appendStreamJsonl({
    required String projectId,
    required String slug,
    required String runId,
    required StreamEventEntity event,
  }) async {
    return left(const ArtifactPersistenceFailure.ioError());
  }
}
