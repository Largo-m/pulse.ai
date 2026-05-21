import 'package:flutter/material.dart';

abstract final class PulseColors {
  static const Color modalBarrierScrim = Color(0x99000000);

  static const Color background = Color(0xFF0A0F1A);
  static const Color surfaceContainerLowest = Color(0xFF050A14);
  static const Color surfaceContainer = Color(0xFF111827);
  static const Color surfaceContainerLow = Color(0xFF0D1C2D);
  static const Color surfaceContainerHighest = Color(0xFF273647);
  static const Color outlineVariant = Color(0xFF424754);
  static const Color outline = Color(0xFF8C909F);
  static const Color onSurface = Color(0xFFD4E4FA);
  static const Color onSurfaceVariant = Color(0xFFC2C6D6);
  static const Color primary = Color(0xFFADC6FF);
  static const Color onPrimary = Color(0xFF002E6A);
  static const Color primaryContainer = Color(0xFF4D8EFF);
  static const Color onPrimaryContainer = Color(0xFF00285D);
  static const Color secondary = Color(0xFFD0BCFF);
  static const Color onSecondary = Color(0xFF3C0091);
  static const Color surfaceContainerHigh = Color(0xFF1C2B3C);
  static const Color tertiary = Color(0xFF4EDEA3);
  static const Color onTertiary = Color(0xFF003824);
  static const Color tertiaryContainer = Color(0xFF00A572);
  static const Color onTertiaryContainer = Color(0xFF00311F);

  static const ColorScheme colorScheme = ColorScheme.dark(
    surface: background,
    onSurface: onSurface,
    primary: primary,
    onPrimary: onPrimary,
    tertiary: tertiary,
    outline: outline,
    surfaceContainerHighest: surfaceContainerHighest,
  );
}
