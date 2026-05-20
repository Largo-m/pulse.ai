final class LocalProjectEntity {
  const LocalProjectEntity({
    required this.id,
    required this.canonicalPath,
    required this.displayName,
    required this.lastAccessedAt,
    this.macosSecurityScopedBookmark,
  });

  final String id;
  final String canonicalPath;
  final String displayName;
  final DateTime lastAccessedAt;
  final String? macosSecurityScopedBookmark;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is LocalProjectEntity &&
            other.id == id &&
            other.canonicalPath == canonicalPath &&
            other.displayName == displayName &&
            other.lastAccessedAt == lastAccessedAt &&
            other.macosSecurityScopedBookmark == macosSecurityScopedBookmark;
  }

  @override
  int get hashCode => Object.hash(
    id,
    canonicalPath,
    displayName,
    lastAccessedAt,
    macosSecurityScopedBookmark,
  );
}
