import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_prd_agent_service_stub.dart';

import '../domain/service/fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('CursorPrdAgentServiceStub', () {
    late FakeCursorCredentialStoreService credentialStore;
    late CursorPrdAgentServiceStub stub;

    setUp(() {
      credentialStore = FakeCursorCredentialStoreService();
      stub = CursorPrdAgentServiceStub(credentialStore: credentialStore);
    });

    test('preflight returns missingCredential when store is empty', () async {
      final Either<Failure, void> result = await stub.preflight();

      expect(result.isLeft(), isTrue);
      result.fold((Failure failure) {
        expect(failure, isA<CursorConnectionFailure>());
        expect(
          (failure as CursorConnectionFailure).code,
          CursorConnectionFailureCode.missingCredential,
        );
      }, (_) => fail('expected left'));
    });

    test('preflight succeeds when credential is stored', () async {
      await credentialStore.write('valid-credential');

      final Either<Failure, void> result = await stub.preflight();

      expect(result.isRight(), isTrue);
    });

    test('preflight treats whitespace-only credential as missing', () async {
      await credentialStore.write('   ');

      final Either<Failure, void> result = await stub.preflight();

      expect(result.isLeft(), isTrue);
    });

    test('watchRun throws UnimplementedError until task_07', () {
      expect(
        () => stub.watchRun('cloud-run-1'),
        throwsA(isA<UnimplementedError>()),
      );
    });

    test('cancelRun throws UnimplementedError until task_07', () {
      expect(
        () => stub.cancelRun('cloud-run-1'),
        throwsA(isA<UnimplementedError>()),
      );
    });

    test('startRun throws UnimplementedError until task_07', () {
      expect(
        () => stub.startRun(
          const PrdRunContext(
            projectId: 'p1',
            slug: 'agent-a',
            canonicalPath: '/repo',
            branchName: 'main',
            composedPrompt: 'build prd',
          ),
        ),
        throwsA(isA<UnimplementedError>()),
      );
    });
  });
}
