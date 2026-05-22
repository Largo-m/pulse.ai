import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/remove_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/validate_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

final class CursorConnectionCubit extends Cubit<CursorConnectionState> {
  CursorConnectionCubit({
    required RunCursorConnectionPreflightUseCase
    runCursorConnectionPreflightUseCase,
    required ValidateCursorCredentialUseCase validateCursorCredentialUseCase,
    required SaveCursorCredentialUseCase saveCursorCredentialUseCase,
    required RemoveCursorCredentialUseCase removeCursorCredentialUseCase,
  }) : _runCursorConnectionPreflightUseCase =
           runCursorConnectionPreflightUseCase,
       _validateCursorCredentialUseCase = validateCursorCredentialUseCase,
       _saveCursorCredentialUseCase = saveCursorCredentialUseCase,
       _removeCursorCredentialUseCase = removeCursorCredentialUseCase,
       super(const CursorConnectionState());

  final RunCursorConnectionPreflightUseCase
  _runCursorConnectionPreflightUseCase;
  final ValidateCursorCredentialUseCase _validateCursorCredentialUseCase;
  final SaveCursorCredentialUseCase _saveCursorCredentialUseCase;
  final RemoveCursorCredentialUseCase _removeCursorCredentialUseCase;

  void resetSettingsSession() {
    emit(
      state.copyWith(
        isDraftTestPassed: false,
        settingsOperation: CursorSettingsOperationStatus.idle,
        clearSettingsFeedback: true,
      ),
    );
  }

  void onDraftCredentialChanged() {
    emit(
      state.copyWith(
        isDraftTestPassed: false,
        settingsOperation: CursorSettingsOperationStatus.idle,
        clearSettingsFeedback: true,
      ),
    );
  }

  Future<void> testDraftCredential(String apiKey) async {
    emit(
      state.copyWith(
        settingsOperation: CursorSettingsOperationStatus.testing,
        isDraftTestPassed: false,
        clearSettingsFeedback: true,
      ),
    );

    final Either<Failure, void> result = await _validateCursorCredentialUseCase(
      apiKey,
    );

    result.fold(
      (Failure failure) {
        emit(
          state.copyWith(
            isDraftTestPassed: false,
            settingsOperation: CursorSettingsOperationStatus.idle,
            settingsFeedbackMessageKey: _settingsFeedbackForFailure(failure),
          ),
        );
      },
      (_) {
        emit(
          state.copyWith(
            isDraftTestPassed: true,
            settingsOperation: CursorSettingsOperationStatus.idle,
            clearSettingsFeedback: true,
          ),
        );
      },
    );
  }

  Future<void> saveDraftCredential(String apiKey) async {
    if (!state.isDraftTestPassed) {
      emit(
        state.copyWith(
          settingsFeedbackMessageKey:
              OrchestratorStrings.cursorSettingsSaveBlockedWithoutTest,
          settingsOperation: CursorSettingsOperationStatus.idle,
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        settingsOperation: CursorSettingsOperationStatus.saving,
        clearSettingsFeedback: true,
      ),
    );

    await _saveCursorCredentialUseCase(apiKey);
    await runPreflight();
  }

  Future<void> removeCredential() async {
    emit(
      state.copyWith(
        settingsOperation: CursorSettingsOperationStatus.removing,
        clearSettingsFeedback: true,
      ),
    );

    await _removeCursorCredentialUseCase();
    await runPreflight();
  }

  Future<void> runPreflight() async {
    emit(
      state.copyWith(
        status: CursorConnectionStatus.checking,
        settingsOperation: CursorSettingsOperationStatus.idle,
      ),
    );

    final Either<Failure, void> result =
        await _runCursorConnectionPreflightUseCase();

    result.fold(
      (Failure failure) {
        emit(_clearSettingsSession(_mapFailure(failure)));
      },
      (_) {
        emit(
          _clearSettingsSession(
            const CursorConnectionState(
              status: CursorConnectionStatus.connected,
            ),
          ),
        );
      },
    );
  }

  CursorConnectionState _clearSettingsSession(
    CursorConnectionState connectionState,
  ) {
    return connectionState.copyWith(
      isDraftTestPassed: false,
      settingsOperation: CursorSettingsOperationStatus.idle,
      clearSettingsFeedback: true,
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

  String _settingsFeedbackForFailure(Failure failure) {
    if (failure is CursorConnectionFailure) {
      switch (failure.code) {
        case CursorConnectionFailureCode.missingCredential:
          return OrchestratorStrings.cursorSettingsMissingCredentialFeedback;
        case CursorConnectionFailureCode.unauthorized:
          return OrchestratorStrings.cursorSettingsUnauthorizedFeedback;
        case CursorConnectionFailureCode.network:
          return OrchestratorStrings.cursorSettingsNetworkFeedback;
        case CursorConnectionFailureCode.unknown:
          return OrchestratorStrings.cursorSettingsUnknownFeedback;
      }
    }

    return OrchestratorStrings.cursorSettingsUnknownFeedback;
  }
}
