import {answerMarkup} from './AnswerMarkup';
import {ModelAnswer} from './ModelAnswer';
export {answerMarkup} from './AnswerMarkup';

/** Plain question/reference text; saved model answers use ModelAnswer. */
export function CaseAnswer({text,final}:{text:string;final?:any[]}) {
  return final === undefined ? answerMarkup(text,true) : <ModelAnswer text={text} final={final}/>;
}
