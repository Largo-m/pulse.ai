enum CursorConnectionStatus {
  initial,
  checking,
  connected,
  disconnected,
  failure,
}

enum CursorSettingsOperationStatus { idle, testing, saving, removing }

final class CursorConnectionState {
  const CursorConnectionState({
    this.status = CursorConnectionStatus.initial,
    this.remediationMessage,
    this.isDraftTestPassed = false,
    this.settingsOperation = CursorSettingsOperationStatus.idle,
    this.settingsFeedbackMessageKey,
  });

  final CursorConnectionStatus status;
  final String? remediationMessage;
  final bool isDraftTestPassed;
  final CursorSettingsOperationStatus settingsOperation;
  final String? settingsFeedbackMessageKey;

  CursorConnectionState copyWith({
    CursorConnectionStatus? status,
    String? remediationMessage,
    bool clearRemediationMessage = false,
    bool? isDraftTestPassed,
    CursorSettingsOperationStatus? settingsOperation,
    String? settingsFeedbackMessageKey,
    bool clearSettingsFeedback = false,
  }) {
    return CursorConnectionState(
      status: status ?? this.status,
      remediationMessage: clearRemediationMessage
          ? null
          : (remediationMessage ?? this.remediationMessage),
      isDraftTestPassed: isDraftTestPassed ?? this.isDraftTestPassed,
      settingsOperation: settingsOperation ?? this.settingsOperation,
      settingsFeedbackMessageKey: clearSettingsFeedback
          ? null
          : (settingsFeedbackMessageKey ?? this.settingsFeedbackMessageKey),
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is CursorConnectionState &&
            other.status == status &&
            other.remediationMessage == remediationMessage &&
            other.isDraftTestPassed == isDraftTestPassed &&
            other.settingsOperation == settingsOperation &&
            other.settingsFeedbackMessageKey == settingsFeedbackMessageKey;
  }

  @override
  int get hashCode => Object.hash(
    status,
    remediationMessage,
    isDraftTestPassed,
    settingsOperation,
    settingsFeedbackMessageKey,
  );

  @override
  String toString() =>
      'CursorConnectionState(status: $status, remediationMessage: $remediationMessage, '
      'isDraftTestPassed: $isDraftTestPassed, settingsOperation: $settingsOperation, '
      'settingsFeedbackMessageKey: $settingsFeedbackMessageKey)';
}
