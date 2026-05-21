final class AdrEntry {
  const AdrEntry({
    required this.fileName,
    required this.sequenceNumber,
    required this.markdown,
  });

  final String fileName;
  final int sequenceNumber;
  final String markdown;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is AdrEntry &&
            other.fileName == fileName &&
            other.sequenceNumber == sequenceNumber &&
            other.markdown == markdown;
  }

  @override
  int get hashCode => Object.hash(fileName, sequenceNumber, markdown);
}
