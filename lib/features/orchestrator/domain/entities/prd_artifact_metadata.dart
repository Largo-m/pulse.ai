final class PrdArtifactMetadata {
  const PrdArtifactMetadata({required this.lastEditedAt, this.sourceRunId});

  final DateTime lastEditedAt;
  final String? sourceRunId;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdArtifactMetadata &&
            other.lastEditedAt == lastEditedAt &&
            other.sourceRunId == sourceRunId;
  }

  @override
  int get hashCode => Object.hash(lastEditedAt, sourceRunId);
}
