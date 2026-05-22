import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/validate_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

void main() {
  group('ValidateCursorCredentialUseCase', () {
    test('returns right when draft credential is valid', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService()
        ..nextPreflightCredentialResult = right(null);
      final ValidateCursorCredentialUseCase useCase =
          ValidateCursorCredentialUseCase(cursorPrdAgentService: service);

      final result = await useCase('cursor-draft-key');

      expect(result.isRight(), isTrue);
    });

    test('returns unauthorized when preflight responds with 401', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService()
        ..nextPreflightCredentialResult = left(
          const CursorConnectionFailure.unauthorized(),
        );
      final ValidateCursorCredentialUseCase useCase =
          ValidateCursorCredentialUseCase(cursorPrdAgentService: service);

      final result = await useCase('invalid-key');

      expect(result.isLeft(), isTrue);
      result.fold(
        (failure) => expect(
          (failure as CursorConnectionFailure).code,
          CursorConnectionFailureCode.unauthorized,
        ),
        (_) => fail('expected failure'),
      );
    });

    test('returns network failure when preflight responds with 5xx', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService()
        ..nextPreflightCredentialResult = left(
          const CursorConnectionFailure.network(),
        );
      final ValidateCursorCredentialUseCase useCase =
          ValidateCursorCredentialUseCase(cursorPrdAgentService: service);

      final result = await useCase('cursor-draft-key');

      expect(result.isLeft(), isTrue);
      result.fold(
        (failure) => expect(
          (failure as CursorConnectionFailure).code,
          CursorConnectionFailureCode.network,
        ),
        (_) => fail('expected failure'),
      );
    });

    test('returns missingCredential when api key is empty', () async {
      final ValidateCursorCredentialUseCase useCase =
          ValidateCursorCredentialUseCase(
            cursorPrdAgentService: FakeCursorPrdAgentService(),
          );

      final result = await useCase('   ');

      expect(result.isLeft(), isTrue);
      result.fold(
        (failure) => expect(
          (failure as CursorConnectionFailure).code,
          CursorConnectionFailureCode.missingCredential,
        ),
        (_) => fail('expected failure'),
      );
    });
  });
}
