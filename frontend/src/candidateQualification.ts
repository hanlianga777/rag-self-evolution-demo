// Current API projects the reassessment into qualification. Older servers send both fields.
export const currentQualification = (result: any) =>
  result?.qualification_reassessment ?? result?.qualification;

export const formerQualification = (result: any) =>
  result?.old_qualification ?? (result?.qualification_reassessment ? result.qualification : undefined);

export const qualificationWord = (value: any) =>
  value?.qualified === true ? '合格' : value?.qualified === false ? '不合格' : '未知';
