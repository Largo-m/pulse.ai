import 'dart:ui';

import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';

final class ImportProjectAtmosphericBackground extends StatelessWidget {
  const ImportProjectAtmosphericBackground({super.key});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Opacity(
        opacity: PulseDimensions.importAtmosphericLayerOpacity,
        child: Stack(
          children: [
            Positioned(
              top: 0,
              right: 0,
              child: _AtmosphericOrb(
                size: PulseDimensions.importAtmosphericBlurLarge,
                color: PulseColors.primary.withValues(
                  alpha: PulseDimensions.importAtmosphericPrimaryAlpha,
                ),
                blurSigma: PulseDimensions.importAtmosphericBlurSigmaLarge,
              ),
            ),
            Positioned(
              bottom: 0,
              left: 0,
              child: _AtmosphericOrb(
                size: PulseDimensions.importAtmosphericBlurMedium,
                color: PulseColors.secondary.withValues(
                  alpha: PulseDimensions.importAtmosphericSecondaryAlpha,
                ),
                blurSigma: PulseDimensions.importAtmosphericBlurSigmaMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

final class _AtmosphericOrb extends StatelessWidget {
  const _AtmosphericOrb({
    required this.size,
    required this.color,
    required this.blurSigma,
  });

  final double size;
  final Color color;
  final double blurSigma;

  @override
  Widget build(BuildContext context) {
    return ImageFiltered(
      imageFilter: ImageFilter.blur(sigmaX: blurSigma, sigmaY: blurSigma),
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
    );
  }
}
