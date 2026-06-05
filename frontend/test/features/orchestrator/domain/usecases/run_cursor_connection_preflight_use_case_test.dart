import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';

import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

void main() {
  group('RunCursorConnectionPreflightUseCase', () {
    test('returns right when preflight succeeds', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService()
        ..nextPreflightResult = right(null);
      final RunCursorConnectionPreflightUseCase useCase =
          RunCursorConnectionPreflightUseCase(cursorPrdAgentService: service);

      final result = await useCase();

      expect(result.isRight(), isTrue);
    });

    test('returns left when preflight fails', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService()
        ..nextPreflightResult = left(
          const CursorConnectionFailure.missingCredential(),
        );
      final RunCursorConnectionPreflightUseCase useCase =
          RunCursorConnectionPreflightUseCase(cursorPrdAgentService: service);

      final result = await useCase();

      expect(result.isLeft(), isTrue);
      result.fold(
        (failure) => expect(failure, isA<CursorConnectionFailure>()),
        (_) => fail('expected failure'),
      );
    });
  });
}
