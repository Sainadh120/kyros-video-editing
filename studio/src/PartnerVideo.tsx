import React from "react";
import { DoctorVideo, DoctorVideoProps } from "./DoctorVideo";

/**
 * The partner-clinic cut.
 *
 * Kyros gets the doctor's content; the doctor's own clinic gets a cut branded
 * for them. The pairing changes every clip — Dr. Bharani with Aster Ramesh one
 * week, Dr. Krishna with Krishna Clinic the next — so nothing about the partner
 * is named here. Their logo, end-card style and hold time all come from
 * `brands.partner` in the staged captions_data.json.
 *
 * Same footage, captions, timing and doctor plate as the Kyros cut. Only the
 * logo slot and the end card differ, which is why both cuts render through one
 * component: fix a caption once and both inherit it.
 */
export type PartnerVideoProps = Omit<DoctorVideoProps, "brandId">;

export const PartnerVideo: React.FC<PartnerVideoProps> = (props) => (
  <DoctorVideo {...props} brandId="partner" />
);

export default PartnerVideo;
