export function streamResponse(result:unknown) {return new Response(`data: ${JSON.stringify({type:'done',result})}\n\n`,{headers:{'Content-Type':'text/event-stream'}});}
