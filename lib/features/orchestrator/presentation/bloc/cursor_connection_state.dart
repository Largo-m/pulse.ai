enum CursorConnectionStatus {
  initial,
  checking,
  connected,
  disconnected,
  failure,
}

final class CursorConnectionState {
  const CursorConnectionState({
    this.status = CursorConnectionStatus.initial,
    this.remediationMessage,
  });

  final CursorConnectionStatus status;
  final String? remediationMessage;

  CursorConnectionState copyWith({
    CursorConnectionStatus? status,
    String? remediationMessage,
    bool clearRemediationMessage = false,
  }) {
    return CursorConnectionState(
      status: status ?? this.status,
      remediationMessage: clearRemediationMessage
          ? null
          : (remediationMessage ?? this.remediationMessage),
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is CursorConnectionState &&
            other.status == status &&
            other.remediationMessage == remediationMessage;
  }

  @override
  int get hashCode => Object.hash(status, remediationMessage);

  @override
  String toString() =>
      'CursorConnectionState(status: $status, remediationMessage: $remediationMessage)';
}
