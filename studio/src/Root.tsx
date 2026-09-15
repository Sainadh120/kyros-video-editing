import React from "react";
import { Composition } from "remotion";
import { DoctorVideo } from "./DoctorVideo";
import { PartnerVideo } from "./PartnerVideo";
import captions from "./captions_data.json";

const { fps, width, height } = captions.meta;
const K = captions.brands.kyros.durationInFrames;
const P = captions.brands.partner.durationInFrames;
const frame = { fps, width, height };

/*
  Four cuts off one edit, from whichever project is currently staged.

    Composed          -> the Kyros video you post
    PartnerComposed   -> the partner-clinic video you post
    TextOverlay       -> transparent caption layer, Kyros cut
    PartnerTextOverlay-> transparent caption layer, partner cut

  Stage a project first (`reels.py stage <slug>`), which swaps in that clip's
  footage, audio, plate, logos and captions_data.json. Render names come from
  the staged slug, so nothing overwrites the last clip's output.
*/
export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Composed"
      component={DoctorVideo}
      durationInFrames={K}
      {...frame}
      defaultProps={{ showVideo: true, transparent: false, brandId: "kyros" as const }}
    />
    <Composition
      id="TextOverlay"
      component={DoctorVideo}
      durationInFrames={K}
      {...frame}
      defaultProps={{ showVideo: false, transparent: true, brandId: "kyros" as const }}
    />
    <Composition
      id="PartnerComposed"
      component={PartnerVideo}
      durationInFrames={P}
      {...frame}
      defaultProps={{ showVideo: true, transparent: false }}
    />
    <Composition
      id="PartnerTextOverlay"
      component={PartnerVideo}
      durationInFrames={P}
      {...frame}
      defaultProps={{ showVideo: false, transparent: true }}
    />
  </>
);
