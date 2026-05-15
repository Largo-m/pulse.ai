import 'package:flutter/material.dart';

import 'tokens/governance_dimensions.dart';

extension GovernanceTextBuildContext on BuildContext {
  TextStyle governanceCtaButtonLabel() {
    final TextStyle? base = Theme.of(this).textTheme.labelMedium;
    return (base ?? const TextStyle()).copyWith(
      fontWeight: FontWeight.w700,
      letterSpacing: GovernanceDimensions.ctaButtonLetterSpacing,
    );
  }
}

abstract final class GovernanceTypography {
  static const TextTheme textTheme = TextTheme(
    displaySmall: TextStyle(
      fontSize: 24,
      height: 32 / 24,
      letterSpacing: -0.02,
      fontWeight: FontWeight.w600,
    ),
    headlineSmall: TextStyle(
      fontSize: 18,
      height: 24 / 18,
      fontWeight: FontWeight.w600,
    ),
    bodyLarge: TextStyle(fontSize: 14, height: 20 / 14),
    bodyMedium: TextStyle(fontSize: 13, height: 18 / 13),
    labelLarge: TextStyle(
      fontSize: 12,
      height: 16 / 12,
      fontWeight: FontWeight.w500,
    ),
    labelMedium: TextStyle(
      fontSize: 11,
      height: 14 / 11,
      letterSpacing: 0.05,
      fontWeight: FontWeight.w500,
      fontFamily: 'monospace',
    ),
  );
}
