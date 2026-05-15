final class LocalProjectEntity {
  const LocalProjectEntity({
    required this.id,
    required this.absolutePath,
    required this.displayName,
    required this.lastAccessedAt,
  });

  final String id;
  final String absolutePath;
  final String displayName;
  final DateTime lastAccessedAt;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is LocalProjectEntity &&
            other.id == id &&
            other.absolutePath == absolutePath &&
            other.displayName == displayName &&
            other.lastAccessedAt == lastAccessedAt;
  }

  @override
  int get hashCode =>
      Object.hash(id, absolutePath, displayName, lastAccessedAt);
}
