import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

final class CursorConnectionCubit extends Cubit<CursorConnectionState> {
  CursorConnectionCubit({
    required RunCursorConnectionPreflightUseCase
    runCursorConnectionPreflightUseCase,
  }) : _runCursorConnectionPreflightUseCase =
           runCursorConnectionPreflightUseCase,
       super(const CursorConnectionState());

  final RunCursorConnectionPreflightUseCase
  _runCursorConnectionPreflightUseCase;

  Future<void> runPreflight() async {
    emit(const CursorConnectionState(status: CursorConnectionStatus.checking));

    final Either<Failure, void> result =
        await _runCursorConnectionPreflightUseCase();

    result.fold(
      (Failure failure) {
        emit(_mapFailure(failure));
      },
      (_) {
        emit(
          const CursorConnectionState(status: CursorConnectionStatus.connected),
        );
      },
    );
  }

  CursorConnectionState _mapFailure(Failure failure) {
    if (failure is CursorConnectionFailure) {
      switch (failure.code) {
        case CursorConnectionFailureCode.missingCredential:
          return const CursorConnectionState(
            status: CursorConnectionStatus.disconnected,
            remediationMessage: OrchestratorStrings
                .cursorConnectionMissingCredentialRemediation,
          );
        case CursorConnectionFailureCode.unauthorized:
          return const CursorConnectionState(
            status: CursorConnectionStatus.failure,
            remediationMessage:
                OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
          );
        case CursorConnectionFailureCode.network:
        case CursorConnectionFailureCode.unknown:
          return const CursorConnectionState(
            status: CursorConnectionStatus.failure,
            remediationMessage:
                OrchestratorStrings.cursorConnectionDisconnectedRemediation,
          );
      }
    }

    return const CursorConnectionState(
      status: CursorConnectionStatus.failure,
      remediationMessage:
          OrchestratorStrings.cursorConnectionDisconnectedRemediation,
    );
  }
}
