import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_adr_list_load_status.dart';

final class PrdAdrListState {
  const PrdAdrListState({
    this.loadStatus = PrdAdrListLoadStatus.idle,
    this.entries = const <AdrEntry>[],
    this.failureMessageKey,
  });

  final PrdAdrListLoadStatus loadStatus;
  final List<AdrEntry> entries;
  final String? failureMessageKey;

  PrdAdrListState copyWith({
    PrdAdrListLoadStatus? loadStatus,
    List<AdrEntry>? entries,
    String? failureMessageKey,
    bool clearFailureMessageKey = false,
  }) {
    return PrdAdrListState(
      loadStatus: loadStatus ?? this.loadStatus,
      entries: entries ?? this.entries,
      failureMessageKey: clearFailureMessageKey
          ? null
          : (failureMessageKey ?? this.failureMessageKey),
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdAdrListState &&
            other.loadStatus == loadStatus &&
            _listEquals(other.entries, entries) &&
            other.failureMessageKey == failureMessageKey;
  }

  @override
  int get hashCode =>
      Object.hash(loadStatus, Object.hashAll(entries), failureMessageKey);

  @override
  String toString() =>
      'PrdAdrListState(loadStatus: $loadStatus, entries: ${entries.length})';
}

bool _listEquals(List<AdrEntry> a, List<AdrEntry> b) {
  if (a.length != b.length) {
    return false;
  }
  for (int index = 0; index < a.length; index++) {
    if (a[index] != b[index]) {
      return false;
    }
  }
  return true;
}
