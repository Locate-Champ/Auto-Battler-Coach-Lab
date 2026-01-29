function callpv(aff_id){window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('js',new Date());gtag('config','G-M7E3P87KRC',{'send_page_view':false,'custom_param1':aff_id,});gtag('event',aff_id,{'send_to':'G-M7E3P87KRC','event_category':'pageview','event_label':aff_id,'value':1,'non_interaction':true});}
function loadGtag(aff_id){gaMeasurementId="G-M7E3P87KRC";if(typeof gtag==='function'){callpv(aff_id);return;}
var script=document.createElement('script');script.async=true;script.src='https://www.googletagmanager.com/gtag/js?id='+gaMeasurementId;window.dataLayer=window.dataLayer||[];window.gtag=function(){dataLayer.push(arguments);};document.head.appendChild(script);script.onload=function(){callpv(aff_id);};script.onerror=function(){console.error('Failed to load gtag.js');};}
function loadblockevent(adunitname){gtag('event','9298809_block',{'send_to':'G-M7E3P87KRC','event_category':'block','event_label':adunitname,'value':1,'non_interaction':true});}
function loadblock(){gtag('event','9298809_block',{'send_to':'G-M7E3P87KRC','event_category':'block','event_label':'9298809_block','value':1,'non_interaction':true});}
function loadclickaff(adunitname,aff_id){gtag('event',aff_id,{'send_to':'G-M7E3P87KRC','event_category':'click','event_label':adunitname,'value':1,'non_interaction':true});}
function loadblockaff(adunitname,aff_id){gtag('event',aff_id,{'send_to':'G-M7E3P87KRC','event_category':'block','event_label':adunitname,'value':1,'non_interaction':true});}
function loadpubstats(bidder,aff_id,price){gtag('event',aff_id,{'send_to':'G-M7E3P87KRC','event_category':'prebidstats','event_label':bidder,'value':price,'non_interaction':true,'timestamp':new Date().getTime()});}
try{if(aff_var==undefined)aff_var=Array();}catch(e){aff_var=Array()}aff_var.push(9298809);if(aff_var.length==1){var time_interval=500;var status=1;var temp;var vs3;var test;var height;var width;var videolabel=Array();var geoedge=0;var geopercent=10;var geoedge=0;var min_view_rtbdemand=0;var min_view=0;var timebased_refresh_rtbdemand=60;var hijackabm=0;var unfilledabm=1;var rtbdemandnewarray={};var residual=1;var residual2=residual;var responsec={};var isConnected=true;var unfilladunitdata={};var hijackdone={};observehijack={};obsrefreshdone={};country_rtb1="IN";conditionblocklogic={};conditionblock='if(conditionblocklogic[id]){if(conditionblocklogic[id]["WW"])country_new="WW";else country_new=country_rtb1;if(!conditionblocklogic[id][country_new])false; else eval(conditionblocklogic[id][country_new]);  }else{if(conditionblocklogic["ALL"] && conditionblocklogic["ALL"]["WW"]){country_new="WW";}else {country_new=country_rtb1;};if(!conditionblocklogic["ALL"] || !conditionblocklogic["ALL"][country_new])false; else eval(conditionblocklogic["ALL"][country_new]);}';var urlrtbdemand=window.location.origin+window.location.pathname;block_segment_url='//rtbcdn.andbeyond.media/block_segment_multi_9298809.js';conditionseg=false;rtbdemandurl=window.location.href;videoid=null;randNumber=0;randNumbervid=1;randNumberinter=1;randNumbercube=0;function showDivIfHidden(div){computedStyle=window.getComputedStyle(div);if(computedStyle.display==='none'){div.style.removeProperty('display');}}
function findMatchingDimensions(test_input){data_desk=[{width:300,height:250},{width:300,height:600}];data_mobile=[{width:300,height:250},{width:300,height:600}];if(window.innerWidth<=767){anddevice='MOBILE';data_device=data_mobile;}
else{anddevice='DESKTOP'
data_device=data_desk;}
for(let i=0;i<data_device.length;i++){for(let j=0;j<test_input.length;j++){if(typeof test_input[j]==='object'&&test_input[j].width===data_device[i].width&&test_input[j].height===data_device[i].height){return{width:test_input[j].width,height:test_input[j].height};}}}
for(let j=0;j<test_input.length;j++){if(typeof test_input[j]==='object'&&test_input[j]!='fluid'&&test_input[j].width&&test_input[j].width!==1&&(anddevice=='DESKTOP'||(anddevice=='MOBILE'&&test_input[j].width!==728&&test_input[j].width!==970))){return{width:test_input[j].width,height:test_input[j].height};}}
return null;}
function settargetkeys(id1,rtbdemandnewarray,flag_active,visible,count,adunit2,type){googletag.cmd.push(function(){if(id1!=undefined){try{id1.setTargeting('prebidtrue','0');id1.setTargeting('adunit',adunit2);if(rtbdemandnewarray.hijackadunitkey==1)
id1.setTargeting('rtbdemandHI','1');else
id1.setTargeting('rtbdemandHI','0');if(rtbdemandnewarray.unfilledadunitkey==1)
id1.setTargeting('rtbdemandUF','1');else
id1.setTargeting('rtbdemandUF','0');if(rtbdemandnewarray.view)
id1.setTargeting('viewpercent',rtbdemandnewarray.view);var refreshkey='other';if(flag_active==undefined||flag_active==0){if(visible==true)
refreshkey='inactivevisible';else
refreshkey='inactiveinvisible';}
else{if(visible==true)
refreshkey='activevisible';else
refreshkey='activeinvisible';}
if(flag_active==undefined||flag_active==0)
id1.setTargeting("active","0");else
id1.setTargeting("active","1");if(visible==true)
id1.setTargeting("visible","1");else
id1.setTargeting("visible","0");if(flag_active==5)
refreshkey='newunit';if(flag_active==4)
refreshkey='intersectionrefresh';if(flag_active==3)
refreshkey='slotrefresh';if(flag_active==2)
refreshkey='instarefresh';if(flag_active==-1)
refreshkey='unfilledfirstlook';if(flag_active==-2)
refreshkey='hijack';id1.setTargeting('refreshtype',refreshkey);var rtbdemandkeyname='activevisible';if((visible==true&&flag_active==1)){rtbdemandkeyname='activevisible';}
if((visible==true&&flag_active==0)){rtbdemandkeyname='inactivevisible';}
if((visible==false&&flag_active==1)){rtbdemandkeyname='activeinvisible';}
if((visible==false&&flag_active==0)){rtbdemandkeyname='inactiveinvisible';}
if(id1.getTargetingKeys().length>0&&id1.getTargetingKeys().includes('refresh1'))
id1.clearTargeting('refresh1');if(id1.getTargetingKeys().length>0&&id1.getTargetingKeys().includes('activevisible'))
id1.clearTargeting('activevisible');if(id1.getTargetingKeys().length>0&&id1.getTargetingKeys().includes('inactivevisible'))
id1.clearTargeting('inactivevisible');if(id1.getTargetingKeys().length>0&&id1.getTargetingKeys().includes('activeinvisible'))
id1.clearTargeting('activeinvisible');if(id1.getTargetingKeys().length>0&&id1.getTargetingKeys().includes('inactiveinvisible'))
id1.clearTargeting('inactiveinvisible');if(type==1&&flag_active!=undefined&&flag_active>=2&&flag_active<=4){if(count>=10)
refreshkey=refreshkey+'10';else
refreshkey=refreshkey+count;}
if(flag_active!=undefined&&(flag_active==-1||flag_active==-2||flag_active>=2)){count=0;if(type==0&&visible==true)
refreshkey='firstlookvisible';if(type==0&&visible==false)
refreshkey='firstlookinvisible';id1.setTargeting('activevisible',refreshkey);}
if(count>0&&type==0){count=0;if(visible==true)
id1.setTargeting('activevisible','firstlookvisible');else
id1.setTargeting('activevisible','firstlookinvisible');}
if(count==1){id1.setTargeting(rtbdemandkeyname,'1');}else if(count==2){id1.setTargeting(rtbdemandkeyname,'2');}else if(count==3){id1.setTargeting(rtbdemandkeyname,'3');}else if(count==4){id1.setTargeting(rtbdemandkeyname,'4');}else if(count==5){id1.setTargeting(rtbdemandkeyname,'5');}else if(count==6){id1.setTargeting(rtbdemandkeyname,'6');}else if(count==7){id1.setTargeting(rtbdemandkeyname,'7');}else if(count==8){id1.setTargeting(rtbdemandkeyname,'8');}else if(count==9){id1.setTargeting(rtbdemandkeyname,'9');}else if(count>=10){id1.setTargeting(rtbdemandkeyname,'10');}else{}
if(count==1)
id1.setTargeting('refresh1','1');if(count==2)
id1.setTargeting('refresh1','2');if(count==3)
id1.setTargeting('refresh1','3');if(count==4)
id1.setTargeting('refresh1','4');if(count==5)
id1.setTargeting('refresh1','5');if(count==6)
id1.setTargeting('refresh1','6');if(count==7)
id1.setTargeting('refresh1','7');if(count==8)
id1.setTargeting('refresh1','8');if(count==9)
id1.setTargeting('refresh1','9');if(count>=10)
id1.setTargeting('refresh1','10');}
catch(e){console.log('EXCEPTION in setting values'+e.stack);}}});}
function adunitnamecheck(newvs2){var adunitnamec=newvs2;let iframeElement=null;var iframesnew=document.getElementsByTagName('iframe');for(let i=0;i<iframesnew.length;i++){var iframe2=iframesnew[i];var iframeIdnew=iframe2.getAttribute('id');if(iframeIdnew&&iframeIdnew.includes('google_ads')){var iframeIdnew=iframe2.parentNode.parentNode.getAttribute('id');if(iframeIdnew===adunitnamec){iframeElement=iframe2;break;}}}
if(iframeElement){try{var iframeIdnew=iframeElement.getAttribute('id');if(iframeIdnew){adunitnamec=iframeIdnew;}}catch(e){console.log('iframeIdnew'+e+'new'+newvs2);}
try{if(adunitnamec.indexOf('google_ads_iframe_')>=0){adunitnamec=adunitnamec.replaceAll('google_ads_iframe_','');pos=adunitnamec.lastIndexOf('/');if(pos>0)
adunitnamec=adunitnamec.substring(pos+1);len=adunitnamec.length;pos123=adunitnamec.substring(len-2,len-1);if(pos123=='_'){adunitnamec=adunitnamec.substring(0,len-2);}
adunitnamec=adunitnamec.substring(0,40);return adunitnamec;}}catch(e){console.log('adunitname'+e+'new'+newvs2);}}}
function gethijack(device,adunit,country,visible,session,size){hijack=0;h2=0;json={};for(var i=0;i<json.length;i++){flag=0;test=json[i];d1=test['device'];a1=test['adunit'];c1=test['country'];v1=test['visible'];s1=test['session'];h1=test['hijack'];si1=test['size'];if((si1=='ALL'||si1.indexOf(size)>=0)&&(d1=='ALL'||d1==device)&&(a1=='ALL'||adunit.indexOf(a1)>=0)&&(c1=='ALL'||c1==country)&&(v1=='ALL'||v1==0||v1==visible)&&(s1=='ALL'||s1==session))
flag=1;if(h1>h2&&flag==1)
h2=h1;}
return h2;}
function firstlookrefreshbid2(vs2,childDiv,rtbdemandnewarray,flag_active,temp_caps){try{if(vs2)hijackdone[vs2]=1;var flag2=1;var flag6=1;var vs3=vs2;vs3=vs3.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');vs3=vs3.replaceAll('\,','');vs3=vs3.replaceAll('\=','');vs3=vs3.replaceAll('\~','');try{time_refreshunit=eval("time_refreshunit"+vs3);nextactive=eval("active"+vs3);nextpassive=eval("passive"+vs3);nextnumber=eval("nextnumber"+vs3);}
catch(e){nextactive=refresh+rtbdemandtotalSeconds1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=timer_refresh;nextnumber=0;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");eval("time_refreshunit"+vs3+" = time_refreshunit");eval("nextnumber"+vs3+" = nextnumber");var sizeflag=0;var idnew2='';var knew=0;var newid=0;var newidflag=0;var norefresh=0;var flag2=1;if(vs2){try{if(country_rtb1==undefined)
country_rtb1='IN';if(vs2.indexOf('rtbdemand')<0)
flag2=blackbox(temp_caps,country_rtb1,city_rtb,city_region,0);else
flag2=0;var tempnew=childDiv.innerHTML;m1html=tempnew;var ele='#'+vs2+' iframe';if(document.getElementById(vs2)){var hitrtbdemand=findInFramesRecnew(document.getElementById(vs2),0);if(hitrtbdemand===1)
flag2=0;}}
catch(e){}
if(vs2&&vs2.indexOf("rtbdemand")<0){var widthheightabm=firstlookadunitsize(vs2,1);var widthm=widthheightabm[0];var heightm=widthheightabm[1];var flag=widthheightabm[2];var position_flag=0;if(getQueryString_val_new("hijack")==1){console.log("vs2"+vs2+"flag"+flag+"flag2"+flag2);}
if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"flag"+flag+"flag2"+flag2);}
vs3=vs2;vs3=vs3.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');vs3=vs3.replaceAll('\,','');vs3=vs3.replaceAll('\=','');vs3=vs3.replaceAll('\~','');try{nextactive=eval("active"+vs3);nextpassive=eval("passive"+vs3);}
catch(e){nextactive=refresh+rtbdemandtotalSeconds1;nextpassive=timer_refresh+timebased_refresh;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");if(flag==1&&flag2==1){slot_vis[vs3]=100;if(flag==1&&newid!=undefined&&newid!=0){eval("time_refreshunit"+vs3+" = timer_refresh");test='<div class="rtbdemand_adunit hijorunfill"><div id="'+newid+'"><scr'+'ipt>googletag.pubads().setTargeting("refresh","1");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+newid+'\'); });</scr'+'ipt></div></div>';refreshBid2(newid,childDiv,1,test,1,widthm,heightm,newidflag,flag6,flag_active,nextactive,0,0,0,rtbdemandnewarray);}else{eval("time_refreshunit"+vs3+" = timer_refresh");test='<div class="rtbdemand_adunit hijorunfill"><div id="'+vs2+'"><scr'+'ipt>googletag.pubads().setTargeting("refresh","1");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt></div></div>';refreshBid2(vs2,childDiv,0,test,1,widthm,heightm,newidflag,flag6,flag_active,nextactive,nextpassive,0,0,rtbdemandnewarray);}}}}}
catch(e){console.log('UNFILL EXCEPTION'+e.stack);}}
function handleIntersectionrefresh(entries,observer){entries.forEach(entry=>{if(entry.isIntersecting){var vs2=null;var vs2=entry.target.id;if(vs2){var adunithijack=vs2;temphijack='';var tempnew=entry.target.innerHTML;tempnew=vs2+tempnew;temphijack=tempnew;temp_caps=tempnew.toUpperCase();var windowwidth=window.innerWidth;if(windowwidth<=767)
var anddevice='MOBILE';else
var anddevice='DESKTOP';var sessionand=0;size='ALL';var hijackreport1=1;var rtbdemandnewarray={};rtbdemandnewarray['unfilledadunitkey']=0;rtbdemandnewarray['hijackadunitkey']=0;rtbdemandnewarray['view']=0;var vs3=vs2;vs3=vs3.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');vs3=vs3.replaceAll('\,','');vs3=vs3.replaceAll('\=','');vs3=vs3.replaceAll('\~','');try{time_refreshunit=eval("time_refreshunit"+vs3);nextactive=eval("active"+vs3);nextpassive=eval("passive"+vs3);nextnumber=eval("nextnumber"+vs3);}
catch(e){nextactive=refresh+rtbdemandtotalSeconds1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=timer_refresh;nextnumber=0;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");eval("time_refreshunit"+vs3+" = time_refreshunit");eval("nextnumber"+vs3+" = nextnumber");diffnew=timer_refresh-time_refreshunit;var widthheightabm=firstlookadunitsize(vs2,0);var widthr=widthheightabm[0];var heightr=widthheightabm[1];var flagin=widthheightabm[2];flag2in=1;if(vs2.indexOf('rtbdemand')<0){flag2in=blackbox(temp_caps,country_rtb1,city_rtb,city_region,0);hiti=findInFramesRecnew(entry.target,0);if(hiti==1)flag2in=0;}
if(vs2&&vs2.indexOf('rtbdemand')<0&&tempnew.indexOf('rtbdemand')>0)flag2in=0;if(flag2in==1&&flagin==1&&diffnew>=25){rect=entry.target.getBoundingClientRect();elementArea=rect.width*rect.height;if(vs2&&vs2.indexOf("rtbdemand")<0)observer.unobserve(entry.target);visibleWidth=Math.min(rect.right,window.innerWidth)-Math.max(rect.left,0);visibleHeight=Math.min(rect.bottom,window.innerHeight)-Math.max(rect.top,0);visibleArea=visibleWidth*visibleHeight;viewabilityPercentage=(visibleArea / elementArea)*100;rtbdemandnewarray['view']=0;if(viewabilityPercentage>=40&&viewabilityPercentage<=50)
rtbdemandnewarray['view']=40;if(viewabilityPercentage>=50&&viewabilityPercentage<=60)
rtbdemandnewarray['view']=50;if(viewabilityPercentage>=60&&viewabilityPercentage<=70)
rtbdemandnewarray['view']=60;if(viewabilityPercentage>=70&&viewabilityPercentage<=80)
rtbdemandnewarray['view']=70;if(viewabilityPercentage>=80&&viewabilityPercentage<=90)
rtbdemandnewarray['view']=80;if(viewabilityPercentage>=90&&viewabilityPercentage<=90)
rtbdemandnewarray['view']=90;if(viewabilityPercentage>=100)
rtbdemandnewarray['view']=100;if(vs2.indexOf('rtbdemand')>=0)
test='<scr'+'ipt> google'+'tag.cmd.'+'push(func'+'tion() {google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt>';else
test='<div class="rtbdemand_adunit interrefresh" style="height:'+heightr+'px; width:'+widthr+'px;overflow:hidden;margin:0 auto;"><div id="'+vs2+'" class="rtbdemandgt" ><scr'+'ipt>google'+'tag.cmd.'+'push(func'+'tion() {google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt></div></div>';if(vs2.indexOf('rtbdemand')>=0)
typein=1;else
typein=0;refreshBid2(vs2,entry.target,typein,test,1,widthr,heightr,0,0,4,nextactive,nextpassive,nextnumber,time_refreshunit,rtbdemandnewarray);}}}});}
function handleIntersection(entries,observer){entries.forEach(entry=>{if(entry.isIntersecting){observer.unobserve(entry.target);var vs2=null;var vs2=entry.target.id;if(vs2){var adunithijack=vs2;if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2);}
temphijack="";var tempnew=entry.target.innerHTML;tempnew=vs2+tempnew;temphijack=tempnew;var temp_caps=tempnew.toUpperCase();var windowwidth=window.innerWidth;if(windowwidth<=767)
var anddevice="MOBILE";else
var anddevice="DESKTOP";var sessionand=0;size="ALL";var hijackreport1=1;var rtbdemandnewarray={};rtbdemandnewarray['unfilledadunitkey']=1;rtbdemandnewarray['hijackadunitkey']=0;rtbdemandnewarray['view']=0;rect=entry.target.getBoundingClientRect();elementArea=rect.width*rect.height;visibleWidth=Math.min(rect.right,window.innerWidth)-Math.max(rect.left,0);visibleHeight=Math.min(rect.bottom,window.innerHeight)-Math.max(rect.top,0);visibleArea=visibleWidth*visibleHeight;viewabilityPercentage=(visibleArea / elementArea)*100;rtbdemandnewarray['view']=0;if(viewabilityPercentage>=40&&viewabilityPercentage<=50)
rtbdemandnewarray['view']=40;if(viewabilityPercentage>=50&&viewabilityPercentage<=60)
rtbdemandnewarray['view']=50;if(viewabilityPercentage>=60&&viewabilityPercentage<=70)
rtbdemandnewarray['view']=60;if(viewabilityPercentage>=70&&viewabilityPercentage<=80)
rtbdemandnewarray['view']=70;if(viewabilityPercentage>=80&&viewabilityPercentage<=90)
rtbdemandnewarray['view']=80;if(viewabilityPercentage>=90&&viewabilityPercentage<=90)
rtbdemandnewarray['view']=90;if(viewabilityPercentage>=100)
rtbdemandnewarray['view']=100;if(unfilledabm==1&&hijackreport1==1){rtbdemandnewarray['unfilledadunitkey']=1;}
if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"unfilledabm"+unfilledabm+"hijackdone[vs2]"+hijackdone[vs2]+"temphijack"+temphijack);}
if(hijackdone[vs2]==undefined&&temphijack.indexOf("rtbdemand")<0&&((unfilledabm==1))){firstlookrefreshbid2(vs2,entry.target,rtbdemandnewarray,-1,temp_caps);}}}});}
function findInFramesRecnew(docrtbdemand,hitrtbdemand){try{var docand=(typeof docrtbdemand==='string')?document.querySelector(docrtbdemand):docrtbdemand;if(docand&&docand.outerHTML&&docand.outerHTML.toLowerCase().indexOf("no_refresh")>=0)return 1;var iframesand=docand.querySelectorAll('iframe');for(var iframeloop=0;iframeloop<iframesand.length;iframeloop++){if(iframesand[iframeloop].contentDocument!=null&&iframesand[iframeloop].contentDocument!=undefined){var rtbdemandfullhtml=iframesand[iframeloop].contentDocument.body.innerHTML;if(rtbdemandfullhtml.indexOf(no_refresh)>=0){docrtbdemand.querySelector('div').classList.add('NO_REFRESH');hitrtbdemand=1;return hitrtbdemand;}
if(iframesand[iframeloop].contentDocument){hitrtbdemand=findInFramesRecnew(iframesand[iframeloop].contentDocument,hitrtbdemand);}
if(hitrtbdemand){return hitrtbdemand;}}}}catch(e){}
return hitrtbdemand;}
function getextrasize(tempnew,vs2){var widthN=1;var heightN=1;var flag=0;var size300=tempnew.indexOf('width="300"');var size250=tempnew.indexOf('height="250"');var size336=tempnew.indexOf('width="336"');var size280=tempnew.indexOf('height="280"');var size600=tempnew.indexOf('height="600"');var size728=tempnew.indexOf('width="728"');var size970=tempnew.indexOf('width="970"');var size160=tempnew.indexOf('width="160"');var size90=tempnew.indexOf('height="90"');var size320=tempnew.indexOf('width="320"');var size50=tempnew.indexOf('height="50"');var size100=tempnew.indexOf('height="100"');var size120=tempnew.indexOf('width="120"');var size480=tempnew.indexOf('height="480"');var size60=tempnew.indexOf('height="60"');var size468=tempnew.indexOf('width="468"');var size1280=tempnew.indexOf('width="1280"');var sizegoogleads=tempnew.indexOf('google_ads_iframe');if(size300>0&&size250>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=300;heightN=250;}
if(size336>0&&size280>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=300;heightN=250;}
if(size300>0&&size600>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=300;heightN=600;}
if(size728>0&&size90>0&&window.innerWidth>768&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=728;heightN=90;}
if(size970>0&&size90>0&&window.innerWidth>768&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=970;heightN=90;}
if(((size970>0&&size250>0)||(size1280>0&&size250>0)||(tempnew.indexOf('width="1140"')>0&&size280>0))&&window.innerWidth>768&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=970;heightN=250;}
if(size160>0&&size600>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=160;heightN=600;}
if(size120>0&&size600>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=120;heightN=600;}
if(size468>0&&(size60>0||size90>0)&&window.innerWidth>768&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=468;heightN=60;}
if(size320>0&&size480>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=320;heightN=480;}
if(size320>0&&size50>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=320;heightN=50;}
if(size300>0&&size100>0&&(sizegoogleads>=0||tempnew.indexOf('aswift')>=0)){flag=1;widthN=300;heightN=100;}
if(flag==0&&tempnew.indexOf('<iframe')>0&&window.innerWidth<=900){try{var divwidth=document.getElementById(vs2).querySelector('iframe').getAttribute('width');var divheight=document.getElementById(vs2).querySelector('iframe').getAttribute('height');if((divwidth>=300&&divwidth<=470)&&(divheight>=220&&divheight<=470)){flag=1;widthN=300;heightN=250;}
if((divwidth>=300&&divwidth<=470)&&(divheight>=500&&divheight<=800)){flag=1;widthN=300;heightN=600;}
if((divwidth>=310&&divwidth<=470)&&(divheight>=40&&divheight<=98)){flag=1;widthN=320;heightN=50;}
if((divwidth>=300&&divwidth<=470)&&(divheight>=99&&divheight<=180)){flag=1;widthN=300;heightN=100;}}
catch(e){console.log('Exception'+e);}}
if(tempnew.indexOf("oop")>=0||tempnew.indexOf("1x1")>=0||tempnew.indexOf("Interstitial")>=0||tempnew.indexOf("interstitial")>=0){flag=0;}
return[widthN,heightN,flag];}
function findClosestSize(desiredWidth,desiredHeight){var sizes=[[300,100],[970,200],[300,600],[970,250],[120,600],[160,600],[468,60],[320,480],[640,480],[300,250],[728,90],[320,50],[970,90]];let closestSize=[1,1];closestDistance=10000;for(let i=0;i<sizes.length;i++){widthsize=sizes[i][0];heightsize=sizes[i][1];if(widthsize<=desiredWidth&&heightsize<=desiredHeight){distance=Math.abs(widthsize-desiredWidth)+Math.abs(heightsize-desiredHeight);if(distance<closestDistance){closestSize=sizes[i];closestDistance=distance;}}}
return closestSize;}
function firstlookadunitsize(vs2,hijack_flag){try{if(vs2){var widthS=1;var heightS=1;var flag=0;unfilled=false;var tempnew;if(flag==0&&hijack_flag==0){tempnew=document.getElementById(vs2).outerHTML;data=getextrasize(tempnew,vs2);widthS=data[0];heightS=data[1];flag=data[2];}
tempnew=unfilladunitdata[vs2];if(tempnew!=undefined&&(flag==0||hijack_flag==1)){widthS=tempnew['sizewidth'];heightS=tempnew['sizeheight'];unfilled=tempnew['unfill'];flag=1;}
temparsize=findClosestSize(widthS,heightS);widthS=temparsize[0];heightS=temparsize[1];var windowwidth=window.innerWidth;if(windowwidth<=767)
anddevice='MOBILE';else
anddevice='DESKTOP';if(anddevice=='MOBILE'&&(width==970||width==728)){widthS=1;heightS=1;flag=0;}
if(width==1)flag=0;return[widthS,heightS,flag,unfilled];}}
catch(e){console.log('EXCEPTION'+e.stack+'vs2'+vs2);return[1,1,0,0];}}
const unfilledobserver=new IntersectionObserver(handleIntersection);const refreshobserver=new IntersectionObserver(handleIntersectionrefresh);try{window.googletag=window.googletag||{cmd:[]};googletag.cmd.push(function(){randnum=Math.floor(Math.random()*5)+1;if(randnum==1){randnum=Math.round(Math.random());if(randnum==1)randNumberinter=1;else randNumberinter=0;if(randnum==1)googletag.pubads().setTargeting("inter","1");else googletag.pubads().setTargeting("inter","0");}
randnum=Math.floor(Math.random()*5)+1;if(randnum==1){randnum=Math.round(Math.random());if(randnum==1)googletag.pubads().setTargeting("cubenew","1");else googletag.pubads().setTargeting("cubenew","0");}});}
catch(e){console.log(e.stack);}
sidesanim=2;maxvariation=1;googlevalue=1;usesame=0;function modifystyle(sides,maxvariation){if(document.getElementById("rtbstyle")){document.head.removeChild(document.getElementById("rtbstyle"));}
styleElement=document.createElement("style");styleElement.id="rtbstyle";if(sides==6&&maxvariation==3){styleElement.textContent=`
           .facertb:hover {
    animation-play-state: paused;
}
.facertb {
position: absolute;
width: 100%;
height: 100%;
border: 1px solid #ccc;
box-sizing: border-box;
background: #fff;
overflow: hidden;
}

.contentrtb {
width: calc(100% - 2px); 
height: calc(100% - 2px);
display: flex;
justify-content: center;
align-items: center;
font-size: 24px;
}



.facertb {
    transform : scale(0.5);
}
.frontrtb { 
    transform: translateZ(75px) scale(0.5);
}
.backrtb { 
    transform: rotateY(180deg) translateZ(75px) scale(0.5);
}
.rightrtb { 
    transform: rotateY(90deg) translateZ(75px) scale(0.5);
}
.leftrtb { 
    transform: rotateY(-90deg) translateZ(75px) scale(0.5);
}
.toprtb { 
    transform: rotateX(90deg) translateZ(63px) scale(0.5);
}
.bottomrtb { 
    transform: rotateX(-90deg) translateZ(63px) scale(0.5);
}


@keyframes rotate {

0%, 100% { transform: rotateX(0) rotateY(0); }
25% { transform: rotateX(90deg) rotateY(0); }
50% { transform: rotateX(90deg) rotateY(90deg); }
75% { transform: rotateX(90deg) rotateY(180deg); }
}
`;}
else if(sides==6&&maxvariation==2){styleElement.textContent=`

         
.facertb {
position: absolute;
width: 100%;
height: 100%;
border: 1px solid #ccc;
box-sizing: border-box;
background: #fff;
overflow: hidden;
}

.contentrtb {
width: calc(100% - 2px);
height: calc(100% - 2px);
display: flex;
justify-content: center;
align-items: center;
font-size: 24px;
}
.facertb {
    transform : scale(0.5);
}
.frontrtb { 
    transform: translateZ(75px) scale(0.5);
}
.backrtb { 
    transform: rotateY(180deg) translateZ(75px) scale(0.5);
}
.rightrtb { 
    transform: rotateY(90deg) translateZ(75px) scale(0.5);
}
.leftrtb { 
    transform: rotateY(-90deg) translateZ(75px) scale(0.5);
}
.toprtb { 
    transform: rotateX(90deg) translateZ(64px) scale(0.5);
}
.bottomrtb { 
    transform: rotateX(-90deg) translateZ(64px) scale(0.5);
}



@keyframes rotate-hover {
    0%, 100% { transform: rotateX(0deg); }
}


@keyframes rotate {

0%, 100% { transform: rotateX(0) rotateY(0); }
25% { transform: rotateX(90deg) rotateY(0); }
50% { transform: rotateX(90deg) rotateY(90deg); }
75% { transform: rotateX(90deg) rotateY(180deg); }
}


.cubertb:hover {
    animation-play-state: paused;
}
`;}
else if(sides==2){styleElement.textContent=`
.frontrtb {
        transform: translateZ(20px) scale(0.7);
}


.facertb {

    position: absolute;
    width: 300px;
    height: 100%;
    background: #fff;
    box-sizing: border-box;
overflow: hidden;
}
@keyframes rotate {
            0%{ transform: rotateY(0deg); }
            100% { transform: rotateY(360deg); }
        }
.backrtb {
    transform: rotateY(180deg) translateZ(20px) scale(0.7);
}
.leftrtb {
    transform: rotateY(-90deg) translateZ(-14px) scale(0.7);
}
.toprtb {
    transform: rotateY(90deg) translateZ(225px) scale(0.7);
}
    `;}
else if(sides==4){styleElement.textContent=`


.facertb {
position: absolute;
width: 100%;
height: 100%;
border: 1px solid #ccc;
background: #fff;
box-sizing: border-box; /* Include border in dimensions */
overflow: hidden;
}

.contentrtb {
width: calc(100% - 2px); /* Account for border width */
height: calc(100% - 2px); /* Account for border width */
display: flex;
justify-content: center;
align-items: center;
font-size: 24px;
}



.facertb {
    transform : scale(0.7);
}
.frontrtb { 
    transform: translateZ(102px) scale(0.7);
}
.backrtb { 
    transform: rotateY(180deg) translateZ(102px) scale(0.7);
}
.rightrtb { 
    transform: rotateY(90deg) translateZ(102px) scale(0.7);
}
.leftrtb { 
  
    transform: rotateY(-90deg)  translateZ(105px) scale(0.7);

}
.toprtb { 

    transform: rotateY(90deg) translateZ(105px) scale(0.7);

}
.bottomrtb { 
    transform: rotateX(-90deg) translateZ(75px) scale(0.7);
}




@keyframes rotate {
0% { transform: rotateY(0); }
100% { transform: rotateY(360deg); }
}
`;}
document.head.appendChild(styleElement);}
var responsec={};function anilogic(slotid,widthr,heightr,slotadid,usesame,maxvariation,sides,googleyes){googletag.cmd.push(function(){modifystyle(sides,maxvariation);existingDiv=document.getElementById(slotid);childDiv=existingDiv.parentElement;childDiv.style.removeProperty("overflow");existingDiv.classList.add("facertb");existingDiv.classList.add("frontrtb");childDiv=existingDiv.parentElement;childDiv.classList.add("cubertb");childDiv.style.width=widthr+"px";childDiv.style.height=heightr+"px";childDiv.style.transformStyle="preserve-3d";childDiv.style.position="relative";childDiv.style.animationPlayState="running";childDiv.style.animation="rotate 10s infinite linear";childDiv.addEventListener("mouseover",function(){this.style.animationPlayState="paused";});childDiv.addEventListener("mouseout",function(){this.style.animationPlayState="running";});adida=Array();adid=null;len=0;if(responsec[widthr]&&responsec[widthr][heightr]){responsec[widthr][heightr]=shuffleArray1(responsec[widthr][heightr]);responsec[widthr][heightr]=shuffleArray(responsec[widthr][heightr]);console.log("SHREYANS"+slotadid+JSON.stringify(responsec));for(i=0;i<responsec[widthr][heightr].length;i++){if(!adida.includes(responsec[widthr][heightr][i]["adid"])&&responsec[widthr][heightr][i]["priority"]>0){adid=responsec[widthr][heightr][i]["adid"];if(len<maxvariation){len++;adida.push(adid);}}}}
if(slotadid!==null&&slotadid!==undefined){adida.push(slotadid.toString());len++;}
if((slotadid==null||slotadid==undefined)&&adida.length>0)
slotadid=adida[0];if(adida.length==0&&googleyes==1){modifystyle(2,maxvariation);sides=0;}
numinit=-1;if(googleyes==1){pos1=Math.floor(Math.random()*5)+1;var slotidcube=slotid.replace("rtbdemand","cube");idextra="cubextra"+slotidcube+widthr+pos1;sizeslot=widthr+"-"+heightr;sizenew=[[widthr,heightr]];textnew="/23312216053/9298809-ANIMATION-"+pos1;var text="googletag.defineSlot(textnew, sizenew,idextra).addService(googletag.pubads());";console.log("TEXTAGAIN"+text);idextra1=null;try{try{idextra1=eval(idextra);}
catch(e){}
if(idextra1==undefined||idextra1==null){idextra1=eval(text);eval(idextra+" = idextra1");}}
catch(e){console.log("CREATION EXCEPTION"+e.stack+"FOR ID");}
i=0;idextra1=null;if(i==0){var newDiv=document.createElement("div");newDiv.setAttribute("width",widthr);newDiv.setAttribute("height",heightr);var newDiv1=document.createElement("div");newDiv1.setAttribute("id",idextra);newDiv1.setAttribute("width",widthr);newDiv1.setAttribute("height",heightr);newDiv.classList.add("NO_REFRESH");newDiv.classList.add("facertb");newDiv.classList.add("backrtb");newDiv.appendChild(newDiv1);var adScript=document.createElement("script");adScript.type="text/javascript";adScript.innerHTML=`
    googletag.cmd.push(function() {
console.log("IDEXTRA"+idextra);
idextra1=eval(idextra);
console.log("IDEXTRA"+idextra1);
if(idextra1!=undefined)
{
 idextra1.setTargeting("extra", "9298809");
         idextra1.setTargeting("prebidtrue", "0");
        googletag.display(idextra);
        googletag.pubads().refresh([idextra1]);
}
    });
`;newDiv1.appendChild(adScript);existingDiv=document.getElementById(slotid);childDiv=existingDiv.parentElement;childDiv.appendChild(newDiv);}}
if(googleyes==1)
ivalue=1;else
ivalue=0;if(sides==0||sides==2){existingDiv=document.getElementById(slotid);childDiv=existingDiv.parentElement;for(i=0;i<2;i++){var newDiv=document.createElement('div');newDiv.setAttribute('id','rtbani');newDiv.setAttribute('width',widthr);newDiv.setAttribute('height',heightr);newDiv.classList.add('facertb');if(i==0)
newDiv.classList.add('leftrtb');if(i==1)
newDiv.classList.add('toprtb');style1='height:250px;width: 60px;margin:0 auto;text-align:center;background: #f9f4f4;;';newDiv.setAttribute('style',style1);childDiv.appendChild(newDiv);}}
for(i=ivalue;i<(sides-1);i++){if(usesame==1){adid=slotadid.toString();}
else{numinit++;if(numinit>(len-1))
numinit=0;adid=adida[numinit];}
existingDiv=document.getElementById(slotid);childDiv=existingDiv.parentElement;var newDiv=document.createElement("div");newDiv.setAttribute("id","rtbani");newDiv.setAttribute("width",widthr);newDiv.setAttribute("height",heightr);newDiv.classList.add("facertb");if(maxvariation==2||maxvariation==1){newDiv.classList.add("facertb");if(i==0)
newDiv.classList.add("backrtb");if(i==1)
newDiv.classList.add("leftrtb");if(i==2)
newDiv.classList.add("toprtb");if(i==3)
newDiv.classList.add("rightrtb");if(i==4)
newDiv.classList.add("bottomrtb");}
else if(maxvariation==3){newDiv.classList.add("facertb");if(i==0)
newDiv.classList.add("bottomrtb");if(i==1)
newDiv.classList.add("rightrtb");if(i==2)
newDiv.classList.add("backrtb");if(i==3)
newDiv.classList.add("toprtb");if(i==4)
newDiv.classList.add("leftrtb");}
else{newDiv.classList.add("facertb");if(i==0)
newDiv.classList.add("backrtb");if(i==1)
newDiv.classList.add("leftrtb");if(i==2)
if(i==3)
newDiv.classList.add("toprtb");if(i==4)
newDiv.classList.add("bottomrtb");}
style1="height:"+heightr+"px; width:"+widthr+"px;margin:0 auto;text-align:center";newDiv.setAttribute("style",style1);var newFrame=document.createElement("iframe");newFrame.setAttribute("id","rtbani");newFrame.setAttribute("FRAMEBORDER","0");newFrame.setAttribute("SCROLLING","no");newFrame.setAttribute("MARGINHEIGHT","0");newFrame.setAttribute("MARGINWIDTH","0");newFrame.setAttribute("TOPMARGIN","0");newFrame.setAttribute("LEFTMARGIN","0");newFrame.setAttribute("ALLOWTRANSPARENCY","true");newFrame.setAttribute("WIDTH","0");newFrame.setAttribute("HEIGHT","0");newDiv.appendChild(newFrame);childDiv.appendChild(newDiv);rtbpbjs.renderAd(newFrame.contentWindow.document,adid);adid1=adid.toString();responsec[widthr][heightr]=changePriority(responsec[widthr][heightr],adid1);}});}
function removalrtb(slotid){if(slotid.indexOf("rtbdemand")>=0){existingDiv=document.getElementById(slotid);existingDiv.parentElement.style.overflow="hidden";if(existingDiv.parentElement.classList.contains("cubertb")){childElements=existingDiv.parentElement.children;len=childElements.length;for(i=0;i<len;i++){sibling=childElements[i];if(!sibling.classList.contains("frontrtb")){sibling.remove();i--;len--;}
else
existingDiv.classList.remove("frontrtb");}
existingDiv.parentElement.classList.remove("cubertb")
if(existingDiv.classList.contains("facertb"))
existingDiv.classList.remove("facertb");existingDiv.parentElement.removeAttribute("style");}}}
function changePriority(responsec,changev){let ads=responsec;rtbtime=Date.now();for(let i=0;i<ads.length;i++){if((ads[i].adid===changev)||(ads[i].expiry_time<=rtbtime)){ads[i].priority=0;}}
return ads;}
function getpriority(num){num=num*1000;if(num<1){num=0;return num;}else if(num>1000){num=1000;}
let normalized=num / 1000;let converted=Math.floor(normalized*1000)+1;return Math.min(converted,1000);}
function shuffleArray1(array){for(let i=array.length-1;i>0;i--){j=Math.floor(Math.random()*(i+1));[array[i],array[j]]=[array[j],array[i]];}
return array;}
function shuffleArray(array){array.sort((a,b)=>b.priority-a.priority);return array;}
var refresh_rtbdemand=30;var number=100;var refresh=30;floorlogic=0;var iframes=0;var machine_rules={};var label_adapter_video={};var label_adapter_display={};var config_rtb={};var adapter_rtb_new={"rtbdemand300":[0]};var home_country="IN";var adunit_network=[];bidder_allowed_native={};bidder_allowed_video={};var getQueryString_val_new=function(field,url){var href=url?url:window.location.href;var reg=new RegExp('[?&]'+field+'=([^&#]*)','i');var string=reg.exec(href);return string?string[1]:null;};function bidder_restrict(flag_active,visible,country_rtb1,special_var){zonename='ASI';try{if(timezonename&&timezonename.toLowerCase().indexOf('europe')>=0)
zonename='EUR';if(timezonename&&timezonename.toLowerCase().indexOf('america')>=0)
zonename='LAT';}catch(e){}
try{if(Countrytimezone&&Countrytimezone.toLowerCase().indexOf('europe')>=0)
zonename='EUR';if(Countrytimezone&&Countrytimezone.toLowerCase().indexOf('america')>=0)
zonename='LAT';}catch(e){}
labelnew=Array();var windowwidth=window.innerWidth;if(windowwidth<=767)
device="MOBILE";else
device="DESKTOP";var restrict_bidder1={};for(var type in restrict_bidder1){restrict_bidder=restrict_bidder1[type];for(var bidder in restrict_bidder){temp_ar=restrict_bidder[bidder];temp_ar_new=temp_ar[country_rtb1];if(temp_ar_new==undefined)
temp_ar_new=temp_ar[zonename];if(temp_ar_new==undefined)
temp_ar_new=temp_ar["ALL"];if(temp_ar_new!=undefined){temp_ar_new1=temp_ar_new[device];if(temp_ar_new1==undefined)
temp_ar_new1=temp_ar_new["ALL"];if(temp_ar_new1!=undefined){keyname_new="";label_temp=temp_ar_new1["label"];keyname_temp=temp_ar_new1["keyname"];if(keyname_temp=="all")
labelnew.push(label_temp);keyname_temp=keyname_temp.split(",");try{if(flag_active==1)
keyname_new="active=1";if(flag_active==0)
keyname_new=keyname_new+";active=0";if(visible==1)
keyname_new=keyname_new+";visible=1";if(visible==0)
keyname_new=keyname_new+";visible=0";if(special_var&&special_var!=undefined)
keyname_new=keyname_new+";"+special_var;}
catch(e){}
for(m=0;m<keyname_temp.length;m++){temp_val=keyname_temp[m];if(keyname_new.indexOf(temp_val)>=0)
labelnew.push(label_temp);}}}}}
return labelnew;}
function isDivCentered(divId){div=document.getElementById(divId);if(!div){return false;}
divRect=div.getBoundingClientRect();windowWidth=window.innerWidth;distanceFromLeft=divRect.left;distanceFromRight=windowWidth-divRect.right;if(window.innerWidth>=768){if(Math.abs((windowWidth/2)-(distanceFromLeft+150))<=220)
return true;else
return false;}
else
return true;}
function callnative(id,context,format,id1,andbparams,idnew12,width,height){try{if(format!=undefined&&format=="native"){hb_native_title=null;hb_native_image=null;if(andbparams["hb_native_image"]!=undefined)
hb_native_image=encodenativeurl(andbparams["hb_native_image"]);if(andbparams["hb_native_title"]!=undefined)
hb_native_title=encodenativeurl(andbparams["hb_native_title"]);id1.setTargeting("hb_width",width);id1.setTargeting("hb_height",height);if(hb_native_image!=undefined)
id1.setTargeting("hb_native_image",hb_native_image);if(hb_native_title!=undefined)
id1.setTargeting("hb_native_title",hb_native_title);}}
catch(e){}}
function encodenativeurl(string){var number="0x";var length=string.length;for(var i=0;i<length;i++)
number+=string.charCodeAt(i).toString(16);return number;}
function actionvideo(ref1,videotype){try{newid=null;newid1=null;blockplayer='none';blockunit='block';if(videotype==1){blockplayer='block';blockunit='none';}
newid=document.getElementById("andplayer");if(newid)
className=newid.className;if(className){var words=className.split(/\s+/);for(var i=0;i<words.length;i++){if(words[i].startsWith("rtbdemand")){newid1=words[i];}}}
if(newid1)
newid1=document.getElementById(newid1);if(newid)
newid.style.display=blockplayer;if(newid1)
newid1.style.display=blockunit;if(videotype==0&&newid){if(newid){classname='.'+newid.id;elements=document.querySelectorAll(classname);elements.forEach(element=>{element.parentNode.removeChild(element);});}}}
catch(e){console.log("VIDEO"+e.stack);}}
function loadaniview(idnew12,hb_uuid,videofallback){idplay='andplayer';idvast="65b44b63f4acced6040db794";unitvast='video';var enew1=document.createElement('div');enew1.setAttribute('id',idplay);enew1.classList.add(idplay);enew1.classList.add(idnew12);if(videofallback==2)
style1='display:block;width: 100%;';else
style1='display:none;width: 100%;';enew1.setAttribute('style',style1);menu=document.getElementById(idnew12);menu.parentNode.insertBefore(enew1,menu);var script=document.createElement('script');script.async=true;script.id='AV'+idvast;script.type='text/javascript';if(hb_uuid)
script.src='https://tg1.aniview.com/api/adserver/spt?AV_TAGID='+idvast+'&AV_PUBLISHERID=659bc91f5e80db7bbe051ffa&AV_CDIM1='+unitvast+'&AV_CUSTOM2='+hb_uuid+'&AV_CUSTOM3='+idnew12;else
script.src='https://tg1.aniview.com/api/adserver/spt?AV_TAGID='+idvast+'&AV_PUBLISHERID=659bc91f5e80db7bbe051ffa&AV_CUSTOM1=custom&AV_CUSTOM3='+idnew12;script.setAttribute('data-player-api','callbackFuncNamertb');script.setAttribute('data-config-api','configOverridertb');enew1.appendChild(script);window.configOverridertb=function(config){config.content.contents=[{"id":"ID1","url":"https://g3v2e3j8.ssl.hwcdn.net/Doritos.mp4","thumbnail":"https://rtbdemand.com/images/logo.png","fallbackUrl":"https://g3v2e3j8.ssl.hwcdn.net/Doritos.mp4","clickThroughUrl":"https://www.indianexpress.com","type":"video","slots":[{"type":"ad","time":0}]},{"thumbnail":"https://rtbdemand.com/images/logo.png","id":"ID2","url":"https://g3v2e3j8.ssl.hwcdn.net/Doritos.mp4","fallbackUrl":"https://g3v2e3j8.ssl.hwcdn.net/Doritos.mp4","clickThroughUrl":"https://www.indianexpress.com","type":"video","slots":[{"type":"ad","time":0}]}];}
window.callbackFuncNamertb=function(config,player){player.on("AdLoaded",function(data){ref1=config.adConfig.ref1.toString();actionvideo(ref1,1);})
player.on("AdReady",function(data){ref1=config.adConfig.ref1.toString();actionvideo(ref1,1);})
player.on("AdStopped",function(data){})
player.on("AdSkipped",function(data){})
player.on("AdClosed",function(data){})
player.on("CloseClicked",function(data){ref1=config.adConfig.ref1.toString();actionvideo(ref1,0);})
player.on("AdImpression",function(data){ref1=config.adConfig.ref1.toString();actionvideo(ref1,1);})
player.on("Inventory",function(data){})
player.on("ContentPlaying",function(data){ref1=config.adConfig.ref1.toString();actionvideo(ref1,1);})
player.on("ContentPaused",function(data){ref1=config.adConfig.ref1.toString();actionvideo(ref1,1);})
player.on("AdError",function(res){if(res&&res.data&&res.data.errorLimit){ref1=config.adConfig.ref1.toString();actionvideo(ref1,0);}});}}
var rtbdemandurl=window.location.origin+window.location.pathname;var getQueryString_val=function(field,url){var href=url?url:window.location.href;var reg=new RegExp('[?&]'+field+'=([^&#]*)','i');var string=reg.exec(href);return string?string[1]:null;};var googletag=googletag||{};googletag.cmd=googletag.cmd||[];googletag.cmd.push(function(){googletag.enableServices();});var newadunitrtb=getQueryString_val('newadunitrtb');var lineitemidcode={};function creativeid1(rtbdemandlineitemID,rtbdemandcreativediv,rtbdemandslotname,rtbdemandcreativeId,rtbdemandadvertiserId,rtbdemandcampaignId){if(rtbdemandlineitemID!=null&&rtbdemandcreativediv.indexOf("rtbdemand")<0){if(lineitemidcode.hasOwnProperty(rtbdemandcreativediv)){delete lineitemidcode[rtbdemandcreativediv];}
var rtbdemandtemp={'abplineItemId':rtbdemandlineitemID,'abpcreativeDIV':rtbdemandcreativediv,'abpslotname':rtbdemandslotname,'abpcreativeID':rtbdemandcreativeId,'abpadvertiserId':rtbdemandadvertiserId,'abpcampaignId':rtbdemandcampaignId};lineitemidcode[rtbdemandcreativediv]=rtbdemandtemp;}}
var adslot88=setInterval(function(){var rtbdemandcreativead=Array();if(window.googletag&&googletag.pubadsReady&&googletag.apiReady){clearInterval(adslot88);googletag.cmd.push(function(){googletag.pubads().addEventListener('slotRenderEnded',function(event){var adslot1=event.slot;var rtbdemandslotname=adslot1.getAdUnitPath().toString();var rtbdemandcreativediv=adslot1.getSlotElementId();var rtbdemandlineitemID=event.lineItemId;var rtbdemandcreativeId=event.creativeId;var rtbdemandadvertiserId=event.advertiserId;var rtbdemandcampaignId=event.campaignId;creativeid1(rtbdemandlineitemID,rtbdemandcreativediv,rtbdemandslotname,rtbdemandcreativeId,rtbdemandadvertiserId,rtbdemandcampaignId);});var slots=googletag.pubads().getSlots();for(var i=0;i<slots.length;i++){var slot=slots[i];var responseInfo=slot.getResponseInformation();if(responseInfo!=null){var rtbdemandlineitemID=responseInfo.sourceAgnosticLineItemId;var rtbdemandcreativeId=responseInfo.sourceAgnosticCreativeId;var rtbdemandadvertiserId=responseInfo.advertiserId;var rtbdemandcampaignId=responseInfo.campaignId;var rtbdemandcreativediv=slot.getSlotElementId();var rtbdemandslotname=slot.getAdUnitPath();creativeid1(rtbdemandlineitemID,rtbdemandcreativediv,rtbdemandslotname,rtbdemandcreativeId,rtbdemandadvertiserId,rtbdemandcampaignId);}}});}},10);var lineitemidtest={};var valuse1=1;var observ={};var slot_vis={};var start_time={};var total_vis={};var country_rtb1;var city_rtb;var city_ip;var city_region;var Countrytimezone;var timedate1;var andstatus300=0;var andstatus3001=0;var prebid_active=1;var newtestunitcount=1;var adlooksstatus=0;var adlooksstatus1=0;var adloox_fraud=0;var rtbdemandadult=0;function calcTime(cityddd,offsetdd){var ddd=new Date();var utcdd=ddd.getTime()+(ddd.getTimezoneOffset()*60000);var nde=new Date(utcdd+(3600000*offsetdd));hoursssss=nde.getHours();return hoursssss;}
var newunitcallback=0;var city_rtb='DELHI';var timezonename='ASIA';var Countrytimezone='ASIA';var city_ip='1234445';var city_region='DL';var country_rtb1='US';const loadDatageo=async(url,timeoutThreshold)=>{try{const controller=new AbortController()
const timeoutId=setTimeout(()=>{controller.abort()},timeoutThreshold)
const response=await fetch(url,{signal:controller.signal,})
clearTimeout(timeoutId)
const data=await response.json()
if(Object.keys(data).length>0){var rtbdemandgeo=data;country_rtb1=rtbdemandgeo["countryCode"].toString().toUpperCase();if(rtbdemandgeo["city"]!=null){city_rtb=rtbdemandgeo["city"].toString().toUpperCase();}else{city_rtb=rtbdemandgeo["countryName"].toString().toUpperCase();}
if(rtbdemandgeo["regionCode"]!=null){city_region=rtbdemandgeo["regionCode"].toString().toUpperCase();}else{city_region=rtbdemandgeo["countryName"].toString().toUpperCase();}
if(rtbdemandgeo["timeZone"]!=null){Countrytimezone=rtbdemandgeo["timeZone"]["id"].toString().toUpperCase();}else{Countrytimezone=rtbdemandgeo["countryName"].toString().toUpperCase();}
if(rtbdemandgeo["timeZone"]!=null){timezonename=rtbdemandgeo["timeZone"]["id"].toString().toUpperCase();}else{timezonename=rtbdemandgeo["countryName"].toString().toUpperCase();}
newunitcallback=1;}
return data;}catch(error){}}
loadDatageo('https://rtbdemand.apiip.net/api/check?accessKey=7ef45bac-167a-4aa8-8c99-bc8a28f80bc5&fields=countryCode,regionCode,regionName,city,timeZone,countryName',2000);var block_url={};var and_geo_block={};var width;var height;var size3001status=1;var size3002status=1;var size3003status=1;var size3004status=1;var size3005status=1;var size3006status=1;var size3007status=1;var size3008status=1;var size3009status=1;var size30010status=1;var size30011status=1;var size30012status=1;var size30013status=1;var size30014status=1;var size30015status=1;var size6001status=1;var size6002status=1;var size6003status=1;var size6004status=1;var size6005status=1;var size1601status=1;var size1602status=1;var size1603status=1;var size1604status=1;var size1201status=1;var size1202status=1;var size1203status=1;var size1204status=1;var size7281status=1;var size7282status=1;var size7283status=1;var size7284status=1;var size7285status=1;var size4681status=1;var size4682status=1;var size4683status=1;var size4684status=1;var size4685status=1;var size9701status=1;var size9702status=1;var size9703status=1;var size9704status=1;var size9705status=1;var size9702501status=1;var size9702502status=1;var size9702503status=1;var size9702504status=1;var size9702505status=1;var size3201status=1;var size3202status=1;var size3203status=1;var size3204status=1;var size3205status=1;var size1001status=1;var size1002status=1;var size1003status=1;var size1004status=1;var size1005status=1;var label_adapter={};var machine_rules="{}";function isInteger(num){return(num^0)===num;}
var tier2=0;var tier3=0;var globalrtbdemand=0;var factor_internal=0;var timebased=60;var timebased_refresh=60;var timer_refresh=0;var factor_visible=1;var factor_tier1=1;var factor_tier2=2;var factor_tier1_text='TIER1';var factor_tier2_text='TIER2_US';var no_refresh='<!--NO_REFRESH-->';var detectPartial=true;var highcpm=0.09;var highcpm1=highcpm;var height;var width;var strategy=0;function myTimer(){timer_refresh=timer_refresh+1;}
var myVar=setInterval(myTimer,1000);String.prototype.replaceAll=function(searchStr,replaceStr){var str=this;searchStr=searchStr.replace(/[-\/\\^$*+?.()|[\]{}]/g,'\\$&');return str.replace(new RegExp(searchStr,'gi'),replaceStr);};function isVisible(elem){if(!(elem instanceof Element))return true;const style=getComputedStyle(elem);if(style.display==='none')return false;if(style.visibility!=='visible')return false;if(style.opacity<0.1)return false;if(elem.offsetWidth+elem.offsetHeight+elem.getBoundingClientRect().height+
elem.getBoundingClientRect().width===0){return false;}
const elemCenter={x:elem.getBoundingClientRect().left+elem.offsetWidth / 2,y:elem.getBoundingClientRect().top+elem.offsetHeight / 2};if(elemCenter.x<0)return false;if(elemCenter.x>(document.documentElement.clientWidth||window.innerWidth))return false;if(elemCenter.y<0)return false;if(elemCenter.y>(document.documentElement.clientHeight||window.innerHeight))return false;let pointContainer=document.elementFromPoint(elemCenter.x,elemCenter.y);if(pointContainer!=null&&pointContainer!=undefined){do{if(pointContainer===elem)return true;}while(pointContainer=pointContainer.parentNode);return false;}return false;}
var randomval1=Math.floor(Math.random()*10)+1;var network1=23312216053;var network2=23312216053;var percent1=10;if(randomval1<=percent1){var namemc=network1;}else{var namemc=network2;}
function bidadjust1(cpm){if(cpm<8){cpm1=cpm;cpm=(cpm).toFixed(2);return cpm;}else{return'8.00';}}
var windowwidth2=window.parent.innerWidth;var PREBID_TIMEOUT_NEW=3000;var floor=0;var ref=refresh;if(!googletag||!googletag.apiReady||googletag.apiready&&!googletag.pubadsReady){var googletag=googletag||{};googletag.cmd=googletag.cmd||[];googletag.cmd.push(function(){googletag.pubads().enableSingleRequest();googletag.enableServices();});}
var rtbpbjs=rtbpbjs||{};rtbpbjs.que=rtbpbjs.que||[];var activeadunit=[{code:"rtbdemand3001",mediaTypes:{banner:{sizes:[[300,250],[250,250],[200,200]],}},bids:[{bidder:"random95",params:{}}],ortb2Imp:{ext:{ae:1},gpid:"rtbdemand3001",data:{pbadslot:"rtbdemand3001"}},},{code:"intercode",mediaTypes:{banner:{sizes:[[300,250],[250,250],[200,200]],}},bids:[{bidder:"random95",params:{}}],ortb2Imp:{ext:{ae:1},gpid:"intercode",data:{pbadslot:"intercode"}},}];var divrtbdemand=document.createElement("div");divrtbdemand.setAttribute("id","trackerrtbdemand");divrtbdemand.style.display="none";divrtbdemand.innerHTML="0";document.head.appendChild(divrtbdemand);var rtbdemandtotalSeconds=0;var rtbdemandtotalSeconds1=1;var rtbdemandtimestop;function rtbdemanddisps(){rtbdemandtotalSeconds++;rtbdemandtotalSeconds1=rtbdemandtotalSeconds;}
function addListenerMulti(element,eventNames,listener){var events=eventNames.split(' ');for(var i=0,iLen=events.length;i<iLen;i++){element.addEventListener(events[i],listener,false);}}
var idleStates=false;var idleTimers=null;addListenerMulti(window,"mousemove mouseover touchmove ontouchstart touchend click mouseup mousedown keydown keypress keyup submit change mouseenter scroll resize dblclick",function(){clearTimeout(idleTimers);if(idleStates==false){rtbdemandtimestop=setInterval(function(){rtbdemanddisps()},1000);}
idleStates=true;idleTimers=setTimeout(function(){clearInterval(rtbdemandtimestop);idleStates=false;},3000);});function blackbox(temp_caps,country_rtb1,city_rtb,city_region,new12){flag2=1;for(var make in and_geo_block){for(var i=0;i<and_geo_block[make].length;i++){var country1=and_geo_block[make][i].country_name;var Adunit1=and_geo_block[make][i].Adunit_country;var city1=and_geo_block[make][i].city_name;var adunit_city1=and_geo_block[make][i].Adunit_city;var state1=and_geo_block[make][i].state_name;var adunit_state1=and_geo_block[make][i].Adunit_state;var Time_city1=and_geo_block[make][i].Time_city;var Time_state1=and_geo_block[make][i].Time_state;var Time_country1=and_geo_block[make][i].Time_country;var Hour_state1=and_geo_block[make][i].Hour_state;var Hour_city1=and_geo_block[make][i].Hour_city;var Hour_country1=and_geo_block[make][i].Hour_country;var country_state=country_rtb1+"_"+city_region;if(country1!=undefined&&Adunit1!=undefined&&Time_country1!=undefined){for(d=0;d<Adunit1.length;d++){var adunit_caps=Adunit1[d].toUpperCase();var norefresh1=temp_caps.indexOf(adunit_caps);for(var kkk=0;kkk<Time_country1.length;kkk++){for(var kk2=0;kk2<Hour_country1.length;kk2++){if(Hour_country1[kk2].timezone!=undefined)
timezone=Hour_country1[kk2].timezone;else
timezone='LOCAL';if(timezone=='LOCAL'){current_hour2=new Date().getHours();}
else{current_hour2=calcTime('Bombay','+5.5');}
if(current_hour2==0)
current_hour2=24;if(current_hour2==1)
current_hour2=25;if(current_hour2==2)
current_hour2=26;if(Time_country1!="NONE"&&Hour_country1!="NONE"&&norefresh1>=0&&country_rtb1==country1&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&norefresh1>=0&&country_rtb1==country1&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1=="NONE"&&Time_country1!="ALL"&&norefresh1>=0&&country_rtb1==country1&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1!="NONE"&&norefresh1>=0&&country1=="ALL"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&norefresh1>=0&&country1=="ALL"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1=="NONE"&&Time_country1!="ALL"&&norefresh1>=0&&country1=="ALL"&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(new12==0){if(Time_country1!="NONE"&&Hour_country1!="NONE"&&Adunit1[d]=="ALL"&&country1=="ALL"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&Adunit1[d]=="ALL"&&country1=="ALL"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1=="NONE"&&Time_country1!="ALL"&&Adunit1[d]=="ALL"&&country1=="ALL"&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1!="NONE"&&Adunit1[d]=="ALL"&&country_rtb1==country1&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&Adunit1[d]=="ALL"&&country_rtb1==country1&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1=="NONE"&&Time_country1!="ALL"&&Adunit1[d]=="ALL"&&country_rtb1==country1&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}}
if(new12==0){if(Time_country1!="NONE"&&Hour_country1!="NONE"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1=="NONE"&&Time_country1!="ALL"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}}
if(Time_country1!="NONE"&&Hour_country1!="NONE"&&norefresh1>=0&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="NONE"&&Hour_country1!="ALL"&&norefresh1>=0&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1!="NONE"&&Hour_country1=="NONE"&&Time_country1!="ALL"&&norefresh1>=0&&country1=="INTERNATIONAL"&&country_rtb1!="IN"&&Time_country1[kkk].from<=timedate1&&Time_country1[kkk].to>=timedate1){flag2=0;}
if(Time_country1=="ALL"&&Hour_country1=="NONE"&&norefresh1>=0&&country_rtb1==country1){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="NONE"&&norefresh1>=0&&country_rtb1==country1){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="ALL"&&norefresh1>=0&&country_rtb1==country1){flag2=0;}
if(Hour_country1!="NONE"&&Time_country1=="ALL"&&norefresh1>=0&&country_rtb1==country1&&Hour_country1[kk2].fromhour<=current_hour2&&Hour_country1[kk2].tohour>=current_hour2){flag2=0;}
if(Time_country1=="ALL"&&Hour_country1=="NONE"&&norefresh1>=0&&country1=="ALL"){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="NONE"&&norefresh1>=0&&country1=="ALL"){flag2=0;}
if(Time_country1=="ALL"&&Hour_country1=="NONE"&&norefresh1>=0&&country1=="ALL"){flag2=0;}
if(Time_country1=="ALL"&&Hour_country1=="ALL"&&norefresh1>=0&&country1=="ALL"){flag2=0;}
if(new12==0){if(Time_country1=="ALL"&&Hour_country1=="NONE"&&Adunit1[d]=="ALL"&&country1=="ALL"){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="NONE"&&Adunit1[d]=="ALL"&&country1=="ALL"){flag2=0;}
if(Time_country1=="ALL"&&Hour_country1=="NONE"&&Adunit1[d]=="ALL"&&country_rtb1==country1){flag2=0;}
if(Time_country1=="NONE"&&Hour_country1=="ALL"&&Adunit1[d]=="ALL"&&country_rtb1==country1){flag2=0;}
if(Time_country1=="ALL"&&Hour_country1=="ALL"&&Adunit1[d]=="ALL"&&country_rtb1==country1){flag2=0;}}
if(new12==0){if(Time_country1=="ALL"&&Hour_country1=="NONE"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="NONE"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="ALL"&&Adunit1[d]=="ALL"&&country1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}}
if(Time_country1=="ALL"&&Hour_country1=="NONE"&&norefresh1>=0&&country1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="NONE"&&norefresh1>=0&&country1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_country1=="ALL"&&Time_country1=="ALL"&&norefresh1>=0&&country1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}}}}}
if(city1!=undefined&&adunit_city1!=undefined&&Time_city1!=undefined){for(var f=0;f<adunit_city1.length;f++){for(var h=0;h<Time_city1.length;h++){var adunitcity_caps=adunit_city1[f].toUpperCase();var norefresh2=temp_caps.indexOf(adunitcity_caps);for(var h2=0;h2<Hour_city1.length;h2++){if(Hour_city1[h2].timezone!=undefined)
timezone=Hour_city1[h2].timezone;else
timezone='LOCAL';if(timezone=='LOCAL'){current_hour1=new Date().getHours();}
else{current_hour1=calcTime('Bombay','+5.5');}
if(current_hour1==0)
current_hour1=24;if(current_hour1==1)
current_hour1=25;if(current_hour1==2)
current_hour1=26;if(Time_city1!="NONE"&&Hour_city1!="NONE"&&norefresh2>=0&&city_rtb==city1&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&norefresh2>=0&&city_rtb==city1&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1=="NONE"&&Time_city1!="ALL"&&norefresh2>=0&&city_rtb==city1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1!="NONE"&&norefresh2>=0&&city1=="ALL"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&norefresh2>=0&&city1=="ALL"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1=="NONE"&&Time_city1!="ALL"&&norefresh2>=0&&city1=="ALL"&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(new12==0){if(Time_city1!="NONE"&&Hour_city1!="NONE"&&adunit_city1[f]=="ALL"&&city1=="ALL"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&adunit_city1[f]=="ALL"&&city1=="ALL"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1=="NONE"&&Time_city1!="ALL"&&adunit_city1[f]=="ALL"&&city1=="ALL"&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1!="NONE"&&adunit_city1[f]=="ALL"&&city_rtb==city1&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&adunit_city1[f]=="ALL"&&city_rtb==city1&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1=="NONE"&&Time_city1!="ALL"&&adunit_city1[f]=="ALL"&&city_rtb==city1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}}
if(new12==0){if(Time_city1!="NONE"&&Hour_city1!="NONE"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1=="NONE"&&Time_city1!="ALL"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}}
if(Time_city1!="NONE"&&Hour_city1!="NONE"&&norefresh2>=0&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="NONE"&&Hour_city1!="ALL"&&norefresh2>=0&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Time_city1!="NONE"&&Hour_city1=="NONE"&&Time_city1!="ALL"&&norefresh2>=0&&city1=="INTERNATIONAL"&&country_rtb1!="IN"&&Time_city1[h].from<=timedate1&&Time_city1[h].to>=timedate1){flag2=0;}
if(Time_city1=="ALL"&&Hour_city1=="NONE"&&norefresh2>=0&&city_rtb==city1){flag2=0;}
if(Hour_city1!="NONE"&&Time_city1=="ALL"&&norefresh2>=0&&city_rtb==city1&&Hour_city1[h2].fromhour<=current_hour1&&Hour_city1[h2].tohour>=current_hour1){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="NONE"&&norefresh2>=0&&city_rtb==city1){flag2=0;}
if(Time_city1=="ALL"&&Hour_city1=="NONE"&&norefresh2>=0&&city1=="ALL"){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="NONE"&&norefresh2>=0&&city1=="ALL"){flag2=0;}
if(Time_city1=="ALL"&&Hour_city1=="NONE"&&norefresh2>=0&&city1=="ALL"){flag2=0;}
if(Time_city1=="ALL"&&Hour_city1=="ALL"&&norefresh2>=0&&city1=="ALL"){flag2=0;}
if(new12==0){if(Time_city1=="ALL"&&Hour_city1=="NONE"&&adunit_city1[f]=="ALL"&&city1=="ALL"){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="NONE"&&adunit_city1[f]=="ALL"&&city1=="ALL"){flag2=0;}
if(Time_city1=="ALL"&&Hour_city1=="NONE"&&adunit_city1[f]=="ALL"&&city_rtb==city1){flag2=0;}
if(Time_city1=="NONE"&&Hour_city1=="ALL"&&adunit_city1[f]=="ALL"&&city_rtb==city1){flag2=0;}
if(Time_city1=="ALL"&&Hour_city1=="ALL"&&adunit_city1[f]=="ALL"&&city_rtb==city1){flag2=0;}}
if(new12==0){if(Time_city1=="ALL"&&Hour_city1=="NONE"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="NONE"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="ALL"&&adunit_city1[f]=="ALL"&&city1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}}
if(Time_city1=="ALL"&&Hour_city1=="NONE"&&norefresh2>=0&&city1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="NONE"&&norefresh2>=0&&city1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_city1=="ALL"&&Time_city1=="ALL"&&norefresh2>=0&&city1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}}}}}
if(state1!=undefined&&adunit_state1!=undefined&&Time_state1!=undefined&&Hour_state1!=undefined){for(c=0;c<adunit_state1.length;c++){var adunit_caps1=adunit_state1[c].toUpperCase();var norefresh3=temp_caps.indexOf(adunit_caps1);for(var kk=0;kk<Time_state1.length;kk++){for(var k2=0;k2<Hour_state1.length;k2++){if(Hour_state1[k2].timezone!=undefined)
timezone=Hour_state1[k2].timezone;else
timezone='LOCAL';if(timezone=='LOCAL'){current_hour=new Date().getHours();}
else{current_hour=calcTime('Bombay','+5.5');}
if(current_hour==0)
current_hour=24;if(current_hour==1)
current_hour=25;if(current_hour==2)
current_hour=26;if(Time_state1!="NONE"&&Hour_state1!="NONE"&&norefresh3>=0&&country_state==state1&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&norefresh3>=0&&country_state==state1&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1=="NONE"&&Time_state1!="ALL"&&norefresh3>=0&&country_state==state1&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1!="NONE"&&norefresh3>=0&&state1=="ALL"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&norefresh3>=0&&state1=="ALL"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1=="NONE"&&Time_state1!="ALL"&&norefresh3>=0&&state1=="ALL"&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(new12==0){if(Time_state1!="NONE"&&Hour_state1!="NONE"&&adunit_state1[c]=="ALL"&&state1=="ALL"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&adunit_state1[c]=="ALL"&&state1=="ALL"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1=="NONE"&&Time_state1!="ALL"&&adunit_state1[c]=="ALL"&&state1=="ALL"&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1!="NONE"&&adunit_state1[c]=="ALL"&&country_state==state1&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&adunit_state1[c]=="ALL"&&country_state==state1&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1=="NONE"&&Time_state1!="ALL"&&adunit_state1[c]=="ALL"&&country_state==state1&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}}
if(new12==0){if(Time_state1!="NONE"&&Hour_state1!="NONE"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1=="NONE"&&Time_state1!="ALL"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}}
if(Time_state1!="NONE"&&Hour_state1!="NONE"&&norefresh3>=0&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Hour_state1!="NONE"&&Time_state1=="NONE"&&Hour_state1!="ALL"&&norefresh3>=0&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1!="NONE"&&Hour_state1=="NONE"&&Time_state1!="ALL"&&norefresh3>=0&&state1=="INTERNATIONAL"&&country_rtb1!="IN"&&Time_state1[kk].from<=timedate1&&Time_state1[kk].to>=timedate1){flag2=0;}
if(Time_state1=="ALL"&&Hour_state1=="NONE"&&norefresh3>=0&&country_state==state1){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="NONE"&&norefresh3>=0&&country_state==state1){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="ALL"&&norefresh3>=0&&country_state==state1){flag2=0;}
if(Hour_state1!="NONE"&&Time_city1=="ALL"&&norefresh3>=0&&country_state==state1&&Hour_state1[k2].fromhour<=current_hour&&Hour_state1[k2].tohour>=current_hour){flag2=0;}
if(Time_state1=="ALL"&&Hour_state1=="NONE"&&norefresh3>=0&&state1=="ALL"){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="NONE"&&norefresh3>=0&&state1=="ALL"){flag2=0;}
if(Time_state1=="ALL"&&Hour_state1=="NONE"&&norefresh3>=0&&state1=="ALL"){flag2=0;}
if(Time_state1=="ALL"&&Hour_state1=="ALL"&&norefresh3>=0&&state1=="ALL"){flag2=0;}
if(new12==0){if(Time_state1=="ALL"&&Hour_state1=="NONE"&&adunit_state1[c]=="ALL"&&state1=="ALL"){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="NONE"&&adunit_state1[c]=="ALL"&&state1=="ALL"){flag2=0;}
if(Time_state1=="ALL"&&Hour_state1=="NONE"&&adunit_state1[c]=="ALL"&&country_state==state1){flag2=0;}
if(Time_state1=="NONE"&&Hour_state1=="ALL"&&adunit_state1[c]=="ALL"&&country_state==state1){flag2=0;}
if(Time_state1=="ALL"&&Hour_state1=="ALL"&&adunit_state1[c]=="ALL"&&country_state==state1){flag2=0;}}
if(new12==0){if(Time_state1=="ALL"&&Hour_state1=="NONE"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="NONE"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="ALL"&&adunit_state1[c]=="ALL"&&state1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}}
if(Time_state1=="ALL"&&Hour_state1=="NONE"&&norefresh3>=0&&state1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="NONE"&&norefresh3>=0&&state1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}
if(Hour_state1=="ALL"&&Time_state1=="ALL"&&norefresh3>=0&&state1=="INTERNATIONAL"&&country_rtb1!="IN"){flag2=0;}}}}}}}
return flag2;}
(function(){var gads=document.createElement('script');gads.type='text/javascript';gads.async=true;var useSSL='https:'==document.location.protocol;gads.src=(useSSL?'https:':'http:')+'//cdn.r9x.in/prebid-custom-rtb.js';var node=document.getElementsByTagName('script')[0];node.parentNode.insertBefore(gads,node);})();rtbpbjs.que.push(function(){rtbpbjs.addAdUnits(activeadunit);});setTimeout(function(){var gads=document.createElement('script');gads.async=true;gads.type='text/javascript';var useSSL='https:'==document.location.protocol;gads.src=(useSSL?'https:':'http:')+'//ads.aralego.com/cookiesync';var node=document.getElementsByTagName('script')[0];},10000);rtbpbjs.que.push(function(){rtbpbjs.setConfig({enableTIDs:true});rtbpbjs.setConfig({aliasSyncEnabled:true});rtbpbjs.setConfig({bidderSequence:"fixed"});rtbpbjs.setConfig({cache:{url:"https://prebid.adnxs.com/pbc/v1/cache",ignoreBidderCacheKey:true}});rtbpbjs.setBidderConfig({"bidders":["magnitertb","rubiconrtb","jambojar","cpmstar","between","tripleartside","triplesectop","triplesecside","openxoutstream","adtellvideo","project-lime-video","spotx","freewheel-ssp","amx","eplanning","smilewanted","adtelligent","adagiortb","districtmDMX","brapp","adkernelAdn","tripleart","openx","gumgum","ix","ixrtb","rtbdemand","adkernel","oftmedia","getapp","33across","triplelift","appnexus"],"config":{"schain":{"validation":"relaxed","config":{"ver":"1.0","complete":1,"nodes":[{"asi":"rtbdemand.com","sid":"231885200711","hp":1}]}}}});rtbpbjs.setBidderConfig({"bidders":["Abmanx","bcmopenx","bcmsharethrough"],"config":{"schain":{"validation":"relaxed","config":{"ver":"1.0","complete":1,"nodes":null}}}});});rtbpbjs.que.push(function(){rtbpbjs.aliasBidder("appnexus","projectagora",{gvlid:1032});rtbpbjs.bidderSettings["projectagora"]={bidCpmAdjustment:function(bidCpm){return bidCpm*0.75;}}});rtbpbjs.que.push(function(){rtbpbjs.setBidderConfig({"bidders":["projectagora"],"config":{"schain":{"validation":"strict","config":{"ver":"1.0","complete":1,"nodes":[{"asi":"andbeyond.media","sid":"","hp":1},{"asi":"projectagora.com","sid":"108968","hp":1}]}}}});rtbpbjs.setBidderConfig({bidders:['oftmedia'],config:{schain:{validation:'relaxed',config:{ver:'1.0',complete:1,nodes:[{'asi':'152media.info','sid':'152M21','hp':1}]}}}});});rtbpbjs.que.push(function(){rtbpbjs.setConfig({useBidCache:true,bidCacheFilterFunction:bid=>bid.mediaType!=='video'});});rtbpbjs.que.push(function(){rtbpbjs.setConfig({paapi:{enabled:true,gpt:{autoconfig:false},defaultForSlots:1,bidders:[],}});});rtbpbjs.que.push(function(){;rtbpbjs.setConfig({userSync:{aliasSyncEnabled:false,filterSettings:{all:{bidders:["smartadserver"],filter:"exclude"}},syncsPerBidder:6,syncDelay:3000,auctionDelay:0}});});rtbpbjs.que.push(function(){rtbpbjs.setConfig({userSync:{aliasSyncEnabled:false,userIds:[{name:'uid2',params:{uid2ServerCookie:'uid2_identity'}},{name:'sharedId',storage:{name:'_sharedID',type:'cookie',expires:30}},{name:"amxId",storage:{type:"html5",name:"amxId",expires:1}},{name:"33acrossId",params:{pid:"0013300001cG13gAAC"},storage:{name:"33acrossId",type:"html5",expires:90,refreshInSeconds:8*3600}},{name:"unifiedId",params:{url:"//match.adsrvr.org/track/rid?ttd_pid=pubmatic&fmt=json"},storage:{type:"html5",name:"rtbpbjs-unifiedid",expires:60}},{name:"id5Id",params:{partner:984},storage:{type:"html5",name:"id5id",expires:90,refreshInSeconds:8*3600}}],syncDelay:5000}});});rtbpbjs.que.push(function(){});rtbpbjs.que.push(function(){rtbpbjs.aliasBidder("appnexus","projectagora");rtbpbjs.aliasBidder("project-lime-video","project-limelight");rtbpbjs.aliasBidder("appnexus","abmxandr");rtbpbjs.aliasBidder("appnexus","rtbxandr");rtbpbjs.aliasBidder("smartyads","smartyvideo");rtbpbjs.aliasBidder("adtelligent","adabm");rtbpbjs.aliasBidder("appnexus","districtm");rtbpbjs.aliasBidder("appnexus","abmapp");rtbpbjs.aliasBidder("appnexus","Abmanx");rtbpbjs.aliasBidder("appnexus","getapp");rtbpbjs.aliasBidder("appnexus","bcmapp");rtbpbjs.aliasBidder("appnexus","brapp");rtbpbjs.aliasBidder("criteo","criteointl");rtbpbjs.aliasBidder("criteo","criteoint");rtbpbjs.aliasBidder("triplelift","tripleartside");rtbpbjs.aliasBidder("triplelift","triplesectop");rtbpbjs.aliasBidder("triplelift","triplesecside");rtbpbjs.aliasBidder("triplelift","tripleliftart");rtbpbjs.aliasBidder("rubicon","rubiconrtb");rtbpbjs.aliasBidder("smilewanted","smilewantedabm");rtbpbjs.aliasBidder("projectagora","projectagorart");rtbpbjs.aliasBidder("adkernel","rtbdemandadk");rtbpbjs.aliasBidder("teads","teadarticle");rtbpbjs.aliasBidder("adagio","adagiortb");rtbpbjs.aliasBidder("adtelligent","adtellvideo");rtbpbjs.aliasBidder("adlivetech","adlivevideo");rtbpbjs.aliasBidder("project-limelight","project-lime-video");rtbpbjs.aliasBidder("smilewanted","smilevideo");rtbpbjs.aliasBidder("appnexus","abmoftmedia");rtbpbjs.aliasBidder("appnexus","oftmedia");rtbpbjs.aliasBidder("amx","abmamx");rtbpbjs.aliasBidder("between","betweenabm");rtbpbjs.aliasBidder("openx","bcmopenx");rtbpbjs.aliasBidder("minutemedia","bcmmedia");rtbpbjs.aliasBidder("sharethrough","bcmsharethrough");rtbpbjs.bidderSettings={standard:{storageAllowed:true,adserverTargeting:[{key:"hb_bidder",val:function(bidResponse){return bidResponse.bidderCode;}},{key:"hb_adid",val:function(bidResponse){widthr=bidResponse.width;heightr=bidResponse.height;if(widthr&&heightr&&bidResponse.adId&&bidResponse.cpm&&bidResponse.cpm>=0.001&&bidResponse.adUnitCode&&bidResponse.ttl&&bidResponse.bidderCode&&bidResponse.bidderCode!="adpone"){if(responsec[widthr]&&responsec[widthr][heightr]){}
else{responsec[widthr]={};responsec[widthr][heightr]=[];}
if(responsec[widthr][heightr].length>10){responsec[widthr][heightr]=shuffleArray1(responsec[widthr][heightr]);responsec[widthr][heightr]=shuffleArray(responsec[widthr][heightr]);responsec[widthr][heightr].pop();}
else{priority1=getpriority(bidResponse.cpm);if(bidResponse.adUnitCode.indexOf("rtbdemand")<0)
priority1=0;expiry_time1=Date.now()+(bidResponse.ttl*1000);responsec[widthr][heightr].push({priority:priority1,adid:bidResponse.adId,cpm:bidResponse.cpm,bidder:bidResponse.bidderCode,ttl:bidResponse.ttl,expiry_time:expiry_time1});}}
return bidResponse.adId;}},{key:"rtb_pb",val:function(bidResponse){var cpm=bidResponse.cpm;if(bidResponse.bidderCode&&bidResponse.bidderCode=="pxyz"&&cpm&&cpm<=1.74)
return"0.00";if(bidResponse.cpm<8){return bidResponse.pbHg;}else
return"8.00";}},{key:"hb_pb",val:function(bidResponse){var cpm=bidResponse.cpm;if(bidResponse.bidderCode&&bidResponse.bidderCode=="pxyz"&&cpm&&cpm<=1.74)
return"0.00";if(bidResponse.cpm<8){return bidResponse.pbHg;}else
return"8.00";}},{key:"hb_format",val:function(bidResponse){mediaType=bidResponse.mediaType;if(bidResponse.bidderCode=="teads")
return"banner";if(bidResponse.bidderCode=="projectagora"||bidResponse.bidderCode=="rtbdemandadk"||bidResponse.bidderCode=="adlivevideo"||bidResponse.bidderCode=="luponmedia"||bidResponse.bidderCode=="adpone"||bidResponse.bidderCode=="adliveplus"||bidResponse.bidderCode=="limelightdigital"||bidResponse.bidderCode=="limelightDigital")
return"amp";try{mediaType=bidResponse.mediaType;if(bidResponse.adUnitCode.indexOf('78059622')>=0)
return'amp';if(mediaType==undefined||mediaType=="banner")
mediaType="banner";}
catch(e){mediaType="banner";}
return mediaType;}},{key:"hb_size",val:function(bidResponse){return bidResponse.size;}}]},};});var debug=getQueryString_val_new('debug');if(debug!=undefined&&debug==1){context1=getQueryString_val_new('context');if(context1==undefined)
context1='regular';console.log('CONTEXT'+context1);var adunitmock=getQueryString_val_new('adunit');if(adunitmock==undefined)
adunitmock='rtbdemand3001';var adUnitsfirst=[{code:adunitmock,mediaTypes:{banner:{sizes:[[300,250]],}},bids:[{bidder:'pubmatic',params:{"publisherId":"156276","adSlot":"pubmatic_test"}}]}];if(context1=='instream'){width1=640;height1=480;}
else{width1=300;height1=250;}
var adUnitsvideo=[{code:adunitmock,sizes:[[640,480],[300,250]],mediaTypes:{video:{playerSize:[[width1,height1]],context:context1}},renderer:{url:'https://acdn.adnxs.com/video/outstream/ANOutstreamVideo.js',backupOnly:true,render:function(bid){adResponse={ad:{video:{content:bid.vastXml,player_height:bid.playerHeight,player_width:bid.playerWidth}}}
bid.renderer.push(()=>{ANOutstreamVideo.renderAd({targetId:bid.adUnitCode,adResponse:adResponse});});}},bids:[{bidder:'avantisvideo',params:{AV_PUBLISHERID:'55b78633181f4603178b4568',AV_CHANNELID:'5d19dfca4b6236688c0a2fc4'}}]}];activeadunit=adUnitsfirst;adUnitand1=adUnitsfirst;if(context1=="instream"||context1=="outstream")
adUnits1=adUnitsvideo;rtbpbjs.que.push(function(){rtbpbjs.addAdUnits(adUnitsfirst);if(context1=="instream"||context1=="outstream"){adUnits1=adUnitsvideo;rtbpbjs.addAdUnits(adUnitsvideo);}});}
googletag.cmd.push(function(){googletag.pubads().addEventListener('slotVisibilityChanged',function(event){try{slot=event.slot;var rtbdemandnewarray={};rtbdemandnewarray['unfilledadunitkey']=0;rtbdemandnewarray['hijackadunitkey']=0;rtbdemandnewarray['view']=0;if(event.inViewPercentage>=40&&event.inViewPercentage<=50)
rtbdemandnewarray['view']=40;if(event.inViewPercentage>=50&&event.inViewPercentage<=60)
rtbdemandnewarray['view']=50;if(event.inViewPercentage>=60&&event.inViewPercentage<=70)
rtbdemandnewarray['view']=60;if(event.inViewPercentage>=70&&event.inViewPercentage<=80)
rtbdemandnewarray['view']=70;if(event.inViewPercentage>=80&&event.inViewPercentage<=90)
rtbdemandnewarray['view']=80;if(event.inViewPercentage>=90&&event.inViewPercentage<=90)
rtbdemandnewarray['view']=90;if(event.inViewPercentage>=100)
rtbdemandnewarray['view']=100;slotid=slot.getSlotElementId();slotid1=slotid;if(event.inViewPercentage>50&&slotid&&slotid.indexOf('cubextra')<0&&slotid.indexOf('intercode')<0){existingDiv=document.getElementById(slotid);slotid=slotid.replaceAll('\/','');slotid=slotid.replaceAll('\_','');slotid=slotid.replaceAll('\-','');slotid=slotid.replaceAll('\.','');slotid=slotid.replaceAll('\(','');slotid=slotid.replaceAll('\)','');slotid=slotid.replaceAll('\,','');slotid=slotid.replaceAll('\=','');slotid=slotid.replaceAll('\~','');try{time_refreshunit=eval("time_refreshunit"+slotid);nextactive=eval("active"+slotid);nextpassive=eval("passive"+slotid);nextnumber=eval("nextnumber"+slotid);}
catch(e){nextactive=refresh+rtbdemandtotalSeconds1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=timer_refresh;nextnumber=0;}
eval("passive"+slotid+" = nextpassive");eval("active"+slotid+" = nextactive");eval("time_refreshunit"+slotid+" = time_refreshunit");eval("nextnumber"+slotid+" = nextnumber");diffnew=timer_refresh-time_refreshunit;widthheightabm=firstlookadunitsize(slotid1,0);widthr=widthheightabm[0];heightr=widthheightabm[1];flagin=widthheightabm[2];if(existingDiv&&existingDiv.innerHTML)
temp=existingDiv.innerHTML+slotid;else
temp='';temp_caps=temp.toUpperCase();flag2in=1;if(slotid1.indexOf('rtbdemand')<0){flag2in=blackbox(temp_caps,country_rtb1,city_rtb,city_region,0);hiti=findInFramesRecnew(existingDiv,0);if(hiti==1)flag2in=0;}
if(flag2in==1&&flagin==1&&diffnew>=25){if(slotid1.indexOf('rtbdemand')>=0)
test='<scr'+'ipt> google'+'tag.cmd.'+'push(func'+'tion() {google'+'tag.displ'+'ay(\''+slotid1+'\'); });</scr'+'ipt>';else
test='<div class="rtbdemand_adunit slotrefresh" style="height:'+heightr+'px; width:'+widthr+'px;overflow:hidden;margin:0 auto;"><div id="'+slotid1+'"><scr'+'ipt>google'+'tag.cmd.'+'push(func'+'tion() {google'+'tag.displ'+'ay(\''+slotid1+'\'); });</scr'+'ipt></div></div>';if(slotid1.indexOf('rtbdemand')>=0)
typein=1;else
typein=0;refreshBid2(slotid1,existingDiv,typein,test,1,widthr,heightr,0,0,3,nextactive,nextpassive,nextnumber,time_refreshunit,rtbdemandnewarray);}}}catch(e){console.log(e.stack);}});googletag.pubads().addEventListener('slotRenderEnded',function(event){slot=event.slot;var responseInfo=slot.getResponseInformation();if(responseInfo&&responseInfo.campaignId&&event.slot.getSlotElementId()&&(event.slot.getSlotElementId().indexOf('rtbdemand')>=0||event.slot.getSlotElementId().indexOf('cubextra')>=0)){cid=responseInfo.campaignId.toString();slotid=slot.getSlotElementId();widthr=1;heightr=1;if(slotid.indexOf('300')>=0){widthr=300;heightr=250;}
if(slotid.indexOf('200')>=0){widthr=200;heightr=200;}
if(slotid.indexOf('336')>=0){widthr=336;heightr=280;}
if(slotid.indexOf('160')>=0){widthr=160;heightr=600;}
if(slotid.indexOf('120')>=0){widthr=120;heightr=600;}
if(slotid.indexOf('600')>=0){widthr=300;heightr=600;}
if(slotid.indexOf('468')>=0){widthr=468;heightr=60;}
if(slotid.indexOf('320480')>=0){widthr=320;heightr=480;}
if(slotid.indexOf('320')>=0&&slotid.indexOf('320480')<0){widthr=320;heightr=50;}
if(slotid.indexOf('970')>=0&&slotid.indexOf('970250')<0){widthr=970;heightr=90;}
if(slotid.indexOf('970250')>=0){widthr=970;heightr=250;}
if(slotid.indexOf('728')>=0){widthr=728;heightr=90;}
existingDiv=document.getElementById(slotid);if(slotid.indexOf('rtbdemand')>=0&&existingDiv&&existingDiv.classList.contains('facertb')){removalrtb(slotid);}
slotadid=null;flag_slot=0;if(responsec&&responsec[widthr]&&responsec[widthr][heightr]&&responsec[widthr][heightr].length>0){if(responseInfo.campaignId&&'2517171502,2517372628,2603903204,2761557483,3005196161,3006755219,2516839106,2516841758,2517371437,2517372469,2517372625,2604715422,2604715437,2760518825,2760519512,2766742075,2767247931,3005196215,3005289535,3006080286,3006752372,3006818101,2604715563,3006755267,2517638787,2517372472,2602629805,3246934727,3248687988,2603909519,3265215797,2450583835'.indexOf(cid)>=0){flag_slot=1;slotadid=slot.getTargeting('hb_adid');if(responsec[widthr]&&responsec[widthr][heightr]&&slotadid){adid1=slotadid.toString();responsec[widthr][heightr]=changePriority(responsec[widthr][heightr],adid1);}}
if(randNumber==1&&(event.campaignId=='2718082302'||event.campaignId=='3544557777'||event.campaignId=='2906230027')&&event.slot.getSlotElementId()&&(event.slot.getSlotElementId().indexOf('rtbdemand')>=0||event.slot.getSlotElementId().indexOf('cubextra')>=0)){responsec[widthr][heightr]=shuffleArray1(responsec[widthr][heightr]);responsec[widthr][heightr]=shuffleArray(responsec[widthr][heightr]);var newDiv=document.createElement('div');newDiv.setAttribute('id','rtbdemiframe');newDiv.setAttribute('width',widthr);newDiv.setAttribute('height',heightr);style1="height:"+heightr+"px; width:"+widthr+"px;margin:0 auto;text-align:center";newDiv.setAttribute('style',style1);var newFrame=document.createElement('iframe');newFrame.setAttribute('id','rtbdemiframe');newFrame.setAttribute('FRAMEBORDER','0');newFrame.setAttribute('SCROLLING','no');newFrame.setAttribute('MARGINHEIGHT','0');newFrame.setAttribute('MARGINWIDTH','0');newFrame.setAttribute('TOPMARGIN','0');newFrame.setAttribute('LEFTMARGIN','0');newFrame.setAttribute('ALLOWTRANSPARENCY','true');newFrame.setAttribute('WIDTH','0');newFrame.setAttribute('HEIGHT','0');newDiv.appendChild(newFrame);document.getElementById(slotid).innerHTML='';document.getElementById(slotid).appendChild(newDiv);adid=responsec[widthr][heightr][0]['adid'];slotadid=adid;if(adid){rtbpbjs.renderAd(newFrame.contentWindow.document,adid);adid1=adid.toString();if(responsec[widthr][heightr][0]['priority']>0){flag_slot=1;var url='https://prebid.andbeyond.media/impben1.php?cid=extra&aff=9298809&publisher_id='+responsec[widthr][heightr][0]['bidder']+'&price='+responsec[widthr][heightr][0]['cpm']+'&type=refresh&priority='+responsec[widthr][heightr][0]['priority']+'&ttl='+responsec[widthr][heightr][0]['ttl'];pixel=document.createElement("img");pixel.src=url;pixel.style.display="none";}
changePriority(responsec[widthr][heightr],adid1);}}}
if(home_country&&country_rtb1&&country_rtb1!='IN'&&widthr==300&&heightr==250&&document.getElementsByClassName('cubertb').length<=1)
animation=1;else
animation=0;if(videoid&&videoid==slotid)
animation=0;if(flag_slot==0)
slotadid=null;existingDiv=document.getElementById(slotid);try{if(slot.getTargeting('refreshtype')=='hijack'||slot.getTargeting('refreshtype')=='unfilledfirstlook')
animation=0;}catch(e){}
if(animation==1&&randNumbercube==1&&event.slot.getSlotElementId().indexOf('intercode')<0&&event.slot.getSlotElementId().indexOf('cubextra')<0&&isVisible(existingDiv)&&(googlevalue==1||(googlevalue==0&&slotadid!=null)))
anilogic(slotid,widthr,heightr,slotadid,usesame,maxvariation,sidesanim,googlevalue);}});});limeload=0;rtbpbjs.que.push(function(){rtbpbjs.onEvent('auctionEnd',function(){if(limeload==0){limeload=1;var iframe=document.createElement("iframe");iframe.src="https://tracker.ads-rtbdemand.com/sync.html";iframe.style.display="none";iframe.width="0";iframe.height="0";document.body.appendChild(iframe);}});});var globalinterval3=setInterval(function(){if(newunitcallback==1){clearInterval(globalinterval3);randnum=Math.floor(Math.random()*5)+1;rtbpbjs.que.push(function(){flag_active=0;visible=0;special_var=null;labelnew=bidder_restrict(flag_active,visible,country_rtb1,special_var);rtbpbjs.setConfig({sizeConfig:[{mediaQuery:'(min-width: 10px)',relevantMediaTypes:['banner'],labels:labelnew}]});});rtbpbjs.que.push(function(){});}},100);function refreshBid1rtb(id,width5,height5){googletag.cmd.push(function(){try{var labelnew=Array();var specialvar="";flag_active=1;visible=1;if(country_rtb1==undefined)
country_rtb1='IN';labelnew=bidder_restrict(flag_active,visible,country_rtb1,specialvar);id1=eval(id);id1.setTargeting("prebidtrue","0");id1.setTargeting("refresh1","0");eval("widthid"+id+" = width");eval("heightid"+id+" = height");try{if(adunit3==undefined)
adunit3=id;}
catch(e){adunit3=id;}
try{temp_caps=this1.innerHTML;}
catch(e){temp_caps=id;}
flagvideo=0;rtbpbjs.que.push(function(){rtbpbjs.requestBids({labels:labelnew,timeout:PREBID_TIMEOUT_NEW,adUnitCodes:[id],bidsBackHandler:function(){try{width1=eval('widthid'+id);height1=eval('heightid'+id);width=width1;height=height1;}
catch(e){}
andstatus3001=1;id1=eval(id);if(id1!=undefined){width=width5;height=height5;id1=eval(id);rtbpbjs.setTargetingForGPTAsync([id]);context="instream";videocode=null;var hb_pb=0;var hb_bidder;var hb_adid;var hb_format;var format;idnew12=id.toString();var andbparams=rtbpbjs.getAdserverTargetingForAdUnitCode(idnew12);if(andbparams!=undefined)
format=andbparams["hb_format"];else
format="banner";videounit=0;contextvideounit='other';if(videounit==1&&(contextvideounit=='instream'||contextvideounit=='oustream'&&format!=undefined&&format=='video')||(format!=undefined&&format=='video'&&(context=='instream'||context=='outstream'))){}else{googletag.pubads().refresh([id1]);}}}});});setTimeout(function(){if(andstatus3001==0){id1=eval(id);googletag.pubads().refresh([id1]);}},5000);}
catch(e){}});}
let options={root:null,rootMargin:"-50px -50px",threshold:0.05};let observer=new IntersectionObserver((entries,ob)=>{entries.forEach(entry=>{target_id=entry.target.id;if(entry.isIntersecting){starttime=entry.time;start_time[target_id]=starttime;entry.target.classList.add("active");}else{entry.target.classList.remove("active");if(start_time[target_id]!=undefined&&start_time[target_id]!=0){endtime=entry.time;if(total_vis[target_id]==undefined)
total_vis[target_id]=0;total_vis[target_id]=total_vis[target_id]+endtime-start_time[target_id];totalvisible1=Math.round(total_vis[target_id]/1000);slot_vis[target_id]=totalvisible1;}}});},options);setTimeout(function(){var locurl2=window.location.href;locurl2=locurl2.replace(/(^\w+:|^)\/\//,'');if(block_url&&block_url.length>0){for(i=0;i<block_url.length;i++){var url22=block_url[i]['url'];if(locurl2.indexOf(url22)>=0){try{if(googletag!=undefined&&googletag.pubads()!=undefined){googletag.pubads().setTargeting("adult","1");rtbdemandadult=1;}}catch(e){console.log('EXCEPTION'+e);}}}}},1000);function encodenativeurl(string){var number="0x";var length=string.length;for(var i=0;i<length;i++)
number+=string.charCodeAt(i).toString(16);return number;}
var onscreenrtbdemand=1;document.addEventListener('visibilitychange',function(){if(document.hidden){onscreenrtbdemand=0;}else{onscreenrtbdemand=1;}});function refreshBid2(id,this1,type,test,factor,width,height,newidflag,flag6,flag_active,nextactive,nextpassive,nextnumber,time_refreshunit,rtbdemandnewarray){googletag.cmd.push(function(){try{if(id.indexOf("rtbdemand72815")>=0||id.indexOf("rtbdemand72810")>=0||id.indexOf("rtbdemand72814")>=0||id.indexOf("rtbdemand72813")>=0||id.indexOf("rtbdemand72812")>=0||id.indexOf("rtbdemand72812")>=0||id.indexOf("rtbdemand72814")>=13||id.indexOf("rtbdemand30018")>=0||id.indexOf("rtbdemand30019")>=0||id.indexOf("rtbdemand30020")>=0||id.indexOf("rtbdemand30021")>=0||id.indexOf("rtbdemand30022")>=0||id.indexOf("rtbdemand30023")>=0||id.indexOf("rtbdemand30024")>=0||id.indexOf("rtbdemand30025")>=0||flag_active==-1||flag_active==-2){adunit3=id;adunit5=id;adunit6=id;var lineitemblocking=1;if(adunit3!=undefined){adunit3=adunit3.replaceAll('\/','');adunit3=adunit3.replaceAll('\_','');adunit3=adunit3.replaceAll('\-','');adunit3=adunit3.replaceAll('\.','');}
var adunit2=adunitnamecheck(id);lineitemblock=document.getElementById(adunit5).getAttribute("id");if(lineitemidcode[lineitemblock]!=undefined){linetemp=lineitemidcode[lineitemblock];abplineitem=linetemp['abpcampaignId'];for(var ii=0;ii<lineitemidtest.length;ii++){if(lineitemidtest[ii]==abplineitem&&lineitemblocking==1){lineitemblocking=0;}}}
andblocktests=0;if(lineitemblocking==0){if(adunit3.indexOf('rtbdemand')<0){try{andblocktests=eval('dividandblocktests'+adunit3);}
catch(e2){eval("dividandblocktests"+adunit3+" = 1");andblocktests=1;loadblockaff(adunitnamecheck(adunit2),"5690121_block");}}}
var html=this1.outerHTML;var demand_timeout;var demand_payout;var ad;var publisher_id;var cid;var crid;var id3;var supply_timeout;var countrefresh=0;var norefresh=-1;var idnew=id;var windowwidth=window.innerWidth;var visible=true;if(windowwidth<700||flag6==1)
visible=isVisible(this1);else
visible=isVisible(this1);flag=1;if(visible==true){flag=1;}
var data;id=id.replaceAll('\/','');id=id.replaceAll('\_','');id=id.replaceAll('\-','');id=id.replaceAll('\.','');try{data=eval('count'+id);}
catch(e){data=0;}
var count=1;if(data==undefined)
count=1;else
count=parseInt(data)+1;eval("count"+id+" = count");tempval=eval("count"+id);countrefresh=count;strategy2=strategy;if(visible==false){success=count/factor_visible;if(Number.isInteger(success)){flag=1;strategy2=0;}
else{strategy2=0;flag=0;}}
if(visible==true&&factor>1){success=count/factor;if(Number.isInteger(success)){flag=1;}
else
flag=0;}
if(norefresh>0)
flag=0;var tempnewmain=unfilladunitdata[adunit5];var unfillednew=tempnewmain['unfill'];if(unfillednew==true){flag=1;flag2=1;}
flag2=1;if(type==0){try{flag2=eval('status'+id+'new');}
catch(e){flag2=1;}}
try{if(id.indexOf('rtbdemand')>=0){vs2new=id.replace('rtbdemand','andplayer');if(document.getElementById(vs2new)&&document.getElementById(vs2new).style.width!='1px')
flag=0;}}
catch(e){}
if((adunit3.indexOf('rtbdemand')>=0||html.indexOf('rtbdemiframe')>0)&&flag==1&&flag2==1&&count<=1000){if(slot_vis[adunit3]>=min_view_rtbdemand){flag2=1;}
else{flag2=2;}}
if(adunit3.indexOf('rtbdemand')<0&&flag==1&&flag2==1&&count<=1000){if(slot_vis[adunit3]>=min_view){flag2=1;}
else{flag2=2;}}
flag4=0;if(flag_active==-1||flag_active==-2){flag2=1;flag=1;residual=0;}else{residual=residual2;}
if(id.indexOf("gpt_")>=0||html.indexOf("gpt_")>=0){flag2=0;}
if((count<=1000&&flag==1&&lineitemblocking==1&&residual==1)&&(rtbdemandadult==1||(flag_active==0&&visible==false&&count>=10&&country_rtb1=="JP"))){flag4=1;try{time_refreshunitnew=eval("time_refreshunitnew"+adunit3);}
catch(e){time_refreshunitnew=0;}
diffnew=timer_refresh-time_refreshunitnew;eval("time_refreshunitnew"+adunit3+" = timer_refresh");if(diffnew<20){flag4=0;}
if(flag4==1&&residual==1){if(flag==1){var randomvaldata=Math.floor(Math.random()*5)+1;if((width==970&&height==250)){id='rtbdemand'+width+height+randomvaldata;}
else if((width==300&&height==100)||(width==300&&height==600)){id='rtbdemand'+height+randomvaldata;}else{id='rtbdemand'+width+randomvaldata;}}
var specialvar="";var labelnew=Array();labelnew=bidder_restrict(flag_active,visible,country_rtb1,specialvar);eval("widthid"+id+" = width");eval("heightid"+id+" = height");try{if(adunit3==undefined)
adunit3=id;}
catch(e){adunit3=id;}
try{temp_caps=this1.innerHTML;}
catch(e){temp_caps=id;}
flagvideo=0;rtbpbjs.que.push(function(){rtbpbjs.requestBids({labels:labelnew,timeout:PREBID_TIMEOUT_NEW,adUnitCodes:[id],bidsBackHandler:function(){try{width1=eval('widthid'+id);height1=eval('heightid'+id);width=width1;height=height1;}
catch(e){}
var params=rtbpbjs.getAdserverTargetingForAdUnitCode(id);if(params&&params['hb_adid']){cpm_final=params['hb_pb'];}
else{cpm_final=0;}
if(cpm_final>0.05&&params['hb_format']=='banner'){slot_vis[adunit3]=0;time_refreshunit=timer_refresh;nextnumber++;eval("active"+adunit3+" = nextactive");eval("passive"+adunit3+" = nextpassive");eval("time_refreshunit"+adunit3+" = time_refreshunit");eval("nextnumber"+adunit3+" = nextnumber");var rtbdemrandom=Math.floor(Math.random()*10000)+1;var newDiv=document.createElement("div");newDiv.setAttribute("id",'rtbdemiframe'+rtbdemrandom+'');newDiv.setAttribute("width",width);newDiv.setAttribute("height",height);style1="height:"+height+"px; width:"+width+"px;margin:0 auto;text-align:center";newDiv.setAttribute("style",style1);var newFrame=document.createElement("iframe");newFrame.setAttribute("id","rtbdemiframe"+rtbdemrandom+"");newFrame.setAttribute("FRAMEBORDER","0");newFrame.setAttribute("SCROLLING","no");newFrame.setAttribute("MARGINHEIGHT","0");newFrame.setAttribute("MARGINWIDTH","0");newFrame.setAttribute("TOPMARGIN","0");newFrame.setAttribute("LEFTMARGIN","0");newFrame.setAttribute("ALLOWTRANSPARENCY","true");newFrame.setAttribute("WIDTH","0");newFrame.setAttribute("HEIGHT","0");newDiv.appendChild(newFrame);this1.innerHTML="";this1.appendChild(newDiv);aff="6534192";var url='https://prebid.andbeyond.media/impben1.php?aff='+aff+'&publisher_id='+params['hb_bidder']+'&price='+params['hb_pb']+'&type=refresh';var pixel='<img src="'+url+'" style="display:none"></img>';this1.insertAdjacentHTML("beforeend",pixel);rtbpbjs.renderAd(newFrame.contentWindow.document,params['hb_adid']);}}});});}}else{if(type==0){if(count<=1000&&flag==1&&flag2==1&&lineitemblocking==1){var data;var counter=1;try{if(width==970&&height==250){data=eval('status'+width+height+'new');counter=parseInt(data)+1;}
else{if((width==300&&height==600)||(width==300&&height==100))
data=eval('status'+height+'new');else
data=eval('status'+width+'new');counter=parseInt(data)+1;}}catch(e){data=1;counter=1;}
if(width==970&&height==250)
eval("status"+width+height+"new"+" = counter");else{if((width==300&&height==600)||(width==300&&height==100))
eval("status"+height+"new"+" = counter");else
eval("status"+width+"new"+" = counter");}
eval("status"+id+"new"+" = 1");try{if(width==970&&height==250){stat=eval('size'+width+height+counter+'status');}else{stat=eval('size'+width+counter+'status');}
if(stat==0)
flag2=0;}
catch(e){flag2=0;}
if(height=="600"&&width=="300"){id2='rtbdemand'+height+counter;}else if(height=="250"&&width=="970"){id2='rtbdemand'+width+height+counter;}
else{id2='rtbdemand'+width+counter;}
if(height=="200"&&width=="970")
id2='rtbdemand'+width+height+counter;if(height=="100"&&width=="300")
id2='rtbdemand'+height+counter;eval("rtbdemanddiv"+id+" = id2");eval("rtbdemandwidth"+id+" = width");eval("rtbdemandheight"+id+" = height");test=test.replaceAll(idnew,id2);id=id2;eval("count"+id+" = countrefresh");}}
if(count<=1000&&flag==1&&flag2==1&&lineitemblocking==1){slot_vis[adunit3]=0;time_refreshunit=timer_refresh;nextnumber++;eval("active"+adunit3+" = nextactive");eval("passive"+adunit3+" = nextpassive");eval("time_refreshunit"+adunit3+" = time_refreshunit");eval("nextnumber"+adunit3+" = nextnumber");try{data=eval('counterefresh'+id);}
catch(e){data=0;}
var count=1;if(data==undefined)
count=1;else
count=parseInt(data)+1;eval("counterefresh"+id+" =count");if(html.indexOf('rtbdemiframe')>0){type=0;}
status_bad=0;id1=null;try{id1=eval(id);if(id1==undefined)
status_bad=1;}
catch(e){status_bad=1;}
var namemc_back=namemc;if(status_bad==1){googletag.cmd.push(function(){aff="6534192";len=id.length;if(len==14){pos1=id.substr(len-2);}
else{pos1=id.substr(len-1);}
text=null;if(id.indexOf('100')>0){width1=300;height1=100;width2=100;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[300, 100]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('300')>0){width1=300;height1=250;width2=width1;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[300, 250],[250, 250],[200, 200]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('336')>0){width1=336;height1=280;width2=width1;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[336,280],[300, 250]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('600')>0){width1=300;height1=600;width2=600;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[300,600]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('468')>0){width1=468;height1=60;width2=468;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[468,60]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('728')>0){width1=728;height1=90;width2=728;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[728,90],[468,60],[600,100],[640,100]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('970')>0){width1=970;height1=90;width2=970;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[970, 90],[728,90]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('640')>0){width1=640;height1=480;width2=640;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[640,480]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('970')>0&&id.indexOf('250')>0){width1=970;height1=250;width2=970250;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[970,250]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('970')>0&&id.indexOf('200')>0){width1=970;height1=200;width2=970200;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[970,200]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('160')>0){width1=160;height1=600;width2=160;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[160, 600],[120, 600]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('120')>0){width1=120;height1=600;width2=120;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[120, 600]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('320')>0&&id.indexOf('100')<0){width1=320;height1=50;width2=width1;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[320, 50]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(id.indexOf('320')>0&&id.indexOf('100')>0){width1=320;height1=100;width2=320100;text='googletag.defineSlot("/'+namemc_back+'/'+aff+'-'+width1+'-'+height1+'-'+pos1+'", ["fluid",[320, 100]], "'+id+'").addService(googletag.pubads())';var positiondiv=aff+'-'+width1+'-'+height1+'-'+pos1;}
if(adunit_network.length>0){name_mc=namemc_back;namemc_new=name_mc;for(var i=0;i<adunit_network.length;i++){if(adunit_network[i].adunit==positiondiv)
namemc_new=adunit_network[i].network;}
if(text!=undefined)
text=text.replaceAll(""+name_mc+"",namemc_new);}
if(text!=undefined){try{id1=eval(text);eval("rtbdemand"+width2+pos1+" = id1");}
catch(e){console.log("CREATION EXCEPTION"+e+'FOR ID'+id);}}});}
var googleadsnewID=this1.getAttribute("id");if(type==0){if(adunit5.indexOf("rtbdemand")>=0){this1.innerHTML="";}else{if(googleadsnewID.indexOf("google_ads")>=0){this1.parentNode.style.removeProperty('display');}else{this1.style.removeProperty('display');this1.innerHTML="";}}}
if(html.indexOf('rtbdemiframe')>0){this1.innerHTML="";}
if((type==0||newidflag==1)&&html.indexOf('rtbdemiframe')<0){if(adunit5.indexOf("rtbdemand")>=0){this1.innerHTML=test;}else{if(googleadsnewID.indexOf("google_ads")>=0){if(html.indexOf("browsi")>0){this1.parentNode.outerHTML=test;}else{this1.outerHTML=test;}}else{this1.innerHTML=test;}}}
if(html.indexOf('rtbdemiframe')>0){this1.innerHTML=test;}
try{settargetkeys(id1,rtbdemandnewarray,flag_active,visible,count,adunit2,type);}
catch(e){console.log('EXCEPTION'+e);}
var labelnew=Array();var specialvar="";labelnew=bidder_restrict(flag_active,visible,country_rtb1,specialvar);if(id!=undefined){}
eval("widthid"+id+" = width");eval("heightid"+id+" = height");try{if(adunit3==undefined)
adunit3=id;}
catch(e){adunit3=id;}
try{temp_caps=this1.innerHTML;}
catch(e){temp_caps=id;}
flagvideo=0;rtbpbjs.que.push(function(){if(id!=undefined){rtbpbjs.requestBids({labels:labelnew,timeout:PREBID_TIMEOUT_NEW,adUnitCodes:[id],bidsBackHandler:function(){try{width1=eval('widthid'+id);height1=eval('heightid'+id);width=width1;height=height1;}
catch(e){}
andstatus300=1;id1=eval(id);idnew12=id.toString();var andbparams=rtbpbjs.getAdserverTargetingForAdUnitCode(idnew12);id1=eval(id);if(id1!=undefined){id1=eval(id);rtbpbjs.setTargetingForGPTAsync([id]);context="instream";videocode=null;var hb_pb=0;var hb_bidder;var hb_adid;var hb_format;var format;idnew12=id.toString();var andbparams=rtbpbjs.getAdserverTargetingForAdUnitCode(idnew12);if(andbparams!=undefined)
format=andbparams["hb_format"];else
format="banner";videounit=0;contextvideounit='other';if(videounit==1&&(contextvideounit=='instream'||contextvideounit=='oustream'&&format!=undefined&&format=='video')||(format!=undefined&&format=='video'&&(context=='instream'||context=='outstream'))){}else{googletag.pubads().refresh([id1]);}}}});}});setTimeout(function(){if(andstatus300==0){if(id!=undefined){id1=eval(id);console.log('REFRESHING AGAIN AS NO PREBID RETURNED');googletag.pubads().refresh([id1]);}}},5000);}}}}
catch(e){console.log(e.stack);console.log('EXCEPTION'+e);id1=eval(id);googletag.pubads().refresh([id1]);}});}
var windowwidth=window.innerWidth;var global_refresh=0;var tier2=0;var newid=0;var flag2=1;refreshval=refresh;number5=0;var refresh_time1=0;var refresh_time=0;var refresh_time2=0;setInterval(function(){timedate1=Math.round((new Date()).getTime()/ 1000);var val1=rtbdemandtotalSeconds1;var weekdays=new Array(7);weekdays[0]="Sunday";weekdays[1]="Monday";weekdays[2]="Tuesday";weekdays[3]="Wednesday";weekdays[4]="Thursday";weekdays[5]="Friday";weekdays[6]="Saturday";var current_date=new Date();var weekday_value=current_date.getDay();success=timer_refresh/timebased_refresh;try{if(Number.isInteger(success)){timeflag=1;highcpm=0.1;}
else{timeflag=0;}}catch(e){console.log('EXCEPTION'+e);}
var sizeflag=0;idnew2='';knew=0;var childDivs=document.querySelectorAll('*[id^="rtbdemand"]');for(j=0;j<childDivs.length;j++){var childDiv=childDivs[j];newid=0;newidflag=0;var norefresh=0;flag2=1;var vs2=null;try{if(childDiv!=undefined&&childDiv!=null)
vs2=childDiv.getAttribute('id');else
vs2=null;}
catch(e){}
if(vs2&&vs2.indexOf("23303239422")<0&&(vs2.indexOf("container")>=0||vs2.indexOf("rtbdemand")>=0||vs2.indexOf("aswift_")>=0||vs2.indexOf("ads-SP300x259_")>=0)){try{if(vs2.indexOf("rtbdemand")<0){if(vs2.indexOf("google_ads_iframe_")>=0){vs2=document.getElementById(vs2).parentNode.getAttribute("id");}}}catch(e){console.log("vs2"+e.stack);}
if(childDiv&&vs2!=undefined&&vs2!=null){var visible22=isVisible(childDiv);if(visible22==undefined){visible22=false;}
vs3=vs2;vs3=vs3.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');if(vs3!=undefined){if(observ[vs3]==undefined){observ[vs3]=1;slot_vis[vs3]=0;}}
if(visible22==true)
slot_vis[vs3]=slot_vis[vs3]+1;try{if(vs2!=undefined&&vs2!=null){var vsinnerhtml=document.getElementById(vs2).outerHTML;if(vsinnerhtml.indexOf('<iframe')<0){slot_vis[vs3]=100;}}}catch(e){}
nextactive=refresh+val1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=0;try{time_refreshunit=eval("time_refreshunit"+vs3);nextnumber=eval("nextnumber"+vs3);nextactive=eval("active"+vs3);nextpassive=eval("passive"+vs3);}
catch(e){nextactive=refresh+val1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=timer_refresh;nextnumber=0;pos=1;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");eval("time_refreshunit"+vs3+" = time_refreshunit");eval("nextnumber"+vs3+" = nextnumber");newflag=0;diff=timer_refresh-time_refreshunit;var diffvalue1=refresh;if(vs2.indexOf('rtbdemand')>=0){diffvalue1=refresh_rtbdemand;}else{diffvalue1=refresh;}
flagnewone=0;if(vs2.indexOf('rtbdemand')>=0||(vs2.indexOf('rtbdemand')<0&&timer_refresh>diffvalue1)){if(vs2.indexOf('rtbdemand')<0&&(visible22==true||vs2=="rtbdemand30020"||vs2=="rtbdemand72810")&&timer_refresh>diffvalue1&&diff>=diffvalue1){flagnewone=1;}
else{if(vs2.indexOf('rtbdemand')>=0&&(visible22==true||vs2=="rtbdemand30020"||vs2=="rtbdemand72810")&&diff>diffvalue1){flagnewone=2;}
else{flagnewone=0;}}
var temp=childDiv.outerHTML+vs2;var temp_caps=temp.toUpperCase();m1html=temp;if(val1==nextactive){if(vs2.indexOf('rtbdemand')>=0)
nextactive=nextactive+refresh_rtbdemand;else
nextactive=nextactive+refresh;if(diff>=diffvalue1){factor_visible=factor_visible;newflag=1;flag_active=1;}}
if((timebased==1&&(nextpassive==timer_refresh)&&nextnumber<number)){if(vs2.indexOf('rtbdemand')>=0)
nextpassive=nextpassive+timebased_refresh_rtbdemand;else
nextpassive=nextpassive+timebased_refresh;if(diff>=diffvalue1){factor_visible=factor_visible;flag_active=0;newflag=1;}}
if(flagnewone==1||flagnewone==2){flag_active=2;newflag=1;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");eval("time_refreshunit"+vs3+" = time_refreshunit");eval("nextnumber"+vs3+" = nextnumber");if(newflag==1&&diff>=diffvalue1){if((diff>=diffvalue1&&nextnumber<=5)||(flag_active==1)){flag6=0;highcpm=highcpm1;if(googletag!=undefined&&googletag.pubads()!=undefined)
googletag.pubads().setTargeting("refresh","0");}
else{if(googletag!=undefined&&googletag.pubads()!=undefined)
googletag.pubads().setTargeting("refresh","1");flag6=1;highcpm=0.1;}
try{if(country_rtb1==undefined)
country_rtb1="JP";if(vs2.indexOf('rtbdemand')<0)
flag2=blackbox(temp_caps,country_rtb1,city_rtb,city_region,0);else
flag2=1;var hitrtbdemand=findInFramesRecnew(document.getElementById(vs2),0);if(hitrtbdemand===1){flag2=0;}}catch(e){}
var flag=0;if(vs2.indexOf('rtbdemand')>=0){flag2=1;flag=1;}
if(temp.indexOf('NO_REFRESH')>=0){flag2=0;}
if(flag==0&&vs2.indexOf("rtbdemand")<0){var adunitsizes=firstlookadunitsize(vs2,0);width=adunitsizes[0];height=adunitsizes[1];flag=adunitsizes[2];}
if(vs2.indexOf("gpt_")>=0){flag2=0;}
rtbdemandnewarray['unfilledadunitkey']=0;rtbdemandnewarray['hijackadunitkey']=0;if(flag2==1){if(flag==1&&newid!=undefined&&newid!=0){if(flag6==1)
test='<div class="rtbdemand_adunit" style="height:'+height+'px; width:'+width+'px;overflow:hidden;margin:0 auto !important;"><div id="'+newid+'"><scr'+'ipt>googletag.pubads().setTargeting("refresh","1");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+newid+'\'); });</scr'+'ipt></div></div>';else
test='<div class="rtbdemand_adunit" style="height:'+height+'px; width:'+width+'px;overflow:hidden;margin:0 auto !important;"><div id="'+newid+'"><scr'+'ipt>googletag.pubads().setTargeting("refresh","0");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+newid+'\'); });</scr'+'ipt></div></div>';refreshBid2(newid,childDiv,1,test,1,width,height,newidflag,flag6,flag_active,nextactive,nextpassive,nextnumber,time_refreshunit,rtbdemandnewarray);}
else{if(vs2.indexOf('rtbdemand')==0||(flag==1&&temp.indexOf('id="rtbdemand')<0)){if(vs2.indexOf('rtbdemand')==0){if(flag6==1)
test='<scr'+'ipt> googletag.pubads().setTargeting("refresh","1");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt>';else
test='<scr'+'ipt> googletag.pubads().setTargeting("refresh","0");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt>';refreshBid2(vs2,childDiv,1,test,1,width,height,newidflag,flag6,flag_active,nextactive,nextpassive,nextnumber,time_refreshunit,rtbdemandnewarray);}
else{if(flag6==1)
test='<div class="rtbdemand_adunit" style="height:'+height+'px; width:'+width+'px;overflow:hidden;margin:0 auto !important;"><div id="'+vs2+'"><scr'+'ipt>googletag.pubads().setTargeting("refresh","1");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt></div></div>';else
test='<div class="rtbdemand_adunit" style="height:'+height+'px; width:'+width+'px;overflow:hidden;margin:0 auto !important;"><div id="'+vs2+'"><scr'+'ipt>googletag.pubads().setTargeting("refresh","0");google'+'tag.cmd.'+'push(func'+'tion() { google'+'tag.displ'+'ay(\''+vs2+'\'); });</scr'+'ipt></div></div>';refreshBid2(vs2,childDiv,0,test,1,width,height,newidflag,flag6,flag_active,nextactive,nextpassive,nextnumber,time_refreshunit,rtbdemandnewarray);}}}}
andblocktest=0;if(flag2==0&&flag==1){if(vs3.indexOf('rtbdemand')<0&&temp.indexOf('rtbdemand')<0){try{andblocktest=eval('dividandblocktest'+vs3);}
catch(e2){eval("dividandblocktest"+vs3+" = 1");andblocktest=1;loadblockaff(adunitnamecheck(vs2),"9298809_block");}}}}}}}}},1000);googletag.cmd.push(function(){len=0;timercheck=0;var slots=googletag.pubads().getSlots();length=slots.length;if(length<=len)
length=0;timercheck++;if(timercheck==1)
len=slots.length;var windowwidth=window.innerWidth;if(windowwidth<=767)
anddevice='MOBILE';else
anddevice='DESKTOP';for(var i=0;i<length;i++){var slot=slots[i];var responseInfo=slot.getResponseInformation();var unfilldivid=slot.getSlotElementId();var sizes=slot.getSizes();var width=1;var height=1;result=findMatchingDimensions(sizes);if(result){width=result.width;height=result.height;}
if(unfilldivid.includes("oop")||unfilldivid.includes("1x1")||unfilldivid.includes("overlay")||unfilldivid.includes("cover")||unfilldivid.includes("interstitial")||unfilldivid.includes("Interstitial")){width=1;height=1;}
if(width==300&&height==50){width=300;height=100;}
var rtbdemandunfill=unfilldivid;var rtbdemandslotname=slot.getAdUnitPath();rtbdemandtempunfill={};rtbdemandunfill=rtbdemandunfill.replaceAll('\/','');rtbdemandunfill=rtbdemandunfill.replaceAll('\_','');rtbdemandunfill=rtbdemandunfill.replaceAll('\-','');rtbdemandunfill=rtbdemandunfill.replaceAll('\.','');rtbdemandunfill=rtbdemandunfill.replaceAll('\(','');rtbdemandunfill=rtbdemandunfill.replaceAll('\)','');rtbdemandunfill=rtbdemandunfill.replaceAll('\,','');rtbdemandunfill=rtbdemandunfill.replaceAll('\=','');rtbdemandunfill=rtbdemandunfill.replaceAll('\~','');if(rtbdemandtempunfill.hasOwnProperty(rtbdemandunfill)){delete rtbdemandtempunfill[rtbdemandunfill];}
rtbdemandtempunfill['divid']=rtbdemandunfill;unfilladunitdata['slotrender']=0;rtbdemandtempunfill['unfill']=false;rtbdemandtempunfill['sizewidth']=width;rtbdemandtempunfill['sizeheight']=height
rtbdemandtempunfill['sizewidth']=width;rtbdemandtempunfill['sizeheight']=height;rtbdemandtempunfill['rtbdemandslotname']=rtbdemandslotname;if(unfilladunitdata[unfilldivid]==undefined){unfilladunitdata[unfilldivid]=rtbdemandtempunfill;}}
var tempnew;var slots=googletag.pubads().getSlots();length=slots.length;for(var i=0;i<length;i++){var slot=slots[i];vs2=slot.getSlotElementId();if(vs2){childDiv=document.getElementById(vs2);}
if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"unfilledabm"+unfilledabm+"hijackdone[vs2]"+hijackdone[vs2]);}
if(vs2&&unfilledabm==1&&childDiv!=null&&observehijack[vs2]==undefined&&vs2.indexOf("rtbdemand")<0&&vs2.indexOf("intercode")<0){if(vs2)tempnew=vs2+childDiv.innerHTML;else tempnew=childDiv.innerHTML;temphijack=tempnew;var temp_caps=tempnew.toUpperCase();var adunithijack=vs2;if(adunithijack!=undefined){if(adunithijack!=null){adunithijack=slot.getAdUnitPath();adunithijack=adunithijack.split('/');adunithijack=adunithijack[adunithijack.length-1];}}
var sizeunfilliframeoogle=tempnew.indexOf("<iframe");var sizeunfilliframeoogle1=tempnew.indexOf("google_ads");var widthheightabm=firstlookadunitsize(vs2,1);var adunitwidthheight=widthheightabm[0]+"X"+widthheightabm[1];if(getQueryString_val_new("unfilldebug")==1){console.log("intersection"+sizeunfilliframeoogle+"sizeunfilliframeoogle1"+sizeunfilliframeoogle1+"widthheightabm[3]"+widthheightabm[3]);}
if(sizeunfilliframeoogle1>0&&(widthheightabm[3]==true||sizeunfilliframeoogle<0)){observehijack[vs2]=adunithijack;if(getQueryString_val_new("unfilldebug")==1){console.log("intersection"+vs2);}
tempnew=childDiv.innerHTML+vs2;temphijack=tempnew;var temp_caps=tempnew.toUpperCase();var windowwidth=window.innerWidth;if(windowwidth<=767)
var anddevice="MOBILE";else
var anddevice="DESKTOP";var sessionand=0;size="ALL";var hijackreport1=1;var rtbdemandnewarray={};rtbdemandnewarray['unfilledadunitkey']=1;rtbdemandnewarray['hijackadunitkey']=0;rtbdemandnewarray['view']=0;if(unfilledabm==1&&hijackreport1==1){rtbdemandnewarray['unfilledadunitkey']=1;}
if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"unfilledabm"+unfilledabm+"hijackdone[vs2]"+hijackdone[vs2]+"temphijack"+temphijack);}
if(hijackdone[vs2]==undefined&&temphijack.indexOf("rtbdemand")<0&&((unfilledabm==1)))
firstlookrefreshbid2(vs2,childDiv,rtbdemandnewarray,-1,temp_caps);}}
if(vs2&&childDiv!=null&&obsrefreshdone[vs2]==undefined&&vs2.indexOf("cubextra")<0&&vs2.indexOf("intercode")<0){var tempnew;if(vs2){tempnew=vs2+childDiv.innerHTML;}else{tempnew=childDiv.innerHTML;}
temphijack=tempnew;var temp_caps=tempnew.toUpperCase();var adunithijack=vs2;if(adunithijack!=undefined){if(adunithijack!=null){adunithijack=slot.getAdUnitPath();adunithijack=adunithijack.split('/');adunithijack=adunithijack[adunithijack.length-1];}}
var sizeunfilliframeoogle=tempnew.indexOf("<iframe");var sizeunfilliframeoogle1=tempnew.indexOf("google_ads");var widthheightabm=firstlookadunitsize(vs2,1);var adunitwidthheight=widthheightabm[0]+"X"+widthheightabm[1];if(vs2){obsrefreshdone[vs2]=adunithijack;refreshobserver.observe(childDiv);vs3=vs2;vs3=vs3.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');vs3=vs3.replaceAll('\,','');vs3=vs3.replaceAll('\=','');vs3=vs3.replaceAll('\~','');if(slot_vis[vs3]==undefined)slot_vis[vs3]=0;if(vs2&&sizeunfilliframeoogle1>0&&(widthheightabm[3]==true||sizeunfilliframeoogle<0)){slot_vis[vs3]=100;showDivIfHidden(childDiv);}
try{time_refreshunit=eval("time_refreshunit"+vs3);nextactive=eval("active"+vs3);nextpassive=eval("passive"+vs3);nextnumber=eval("nextnumber"+vs3);}
catch(e){nextactive=refresh+rtbdemandtotalSeconds1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=timer_refresh;nextnumber=0;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");eval("time_refreshunit"+vs3+" = time_refreshunit");eval("nextnumber"+vs3+" = nextnumber");}}}});googletag.cmd.push(function(){googletag.pubads().addEventListener("slotRenderEnded",function(event){var adslot1=event.slot;var unfilldivid=adslot1.getSlotElementId();var rtbdemandunfill=unfilldivid;var rtbdemandslotname=adslot1.getAdUnitPath();setsize=0;size=event.size;var windowwidth=window.innerWidth;if(windowwidth<=767)
anddevice='MOBILE';else
anddevice='DESKTOP';if(event.size&&event.size.length>0){size=event.size[0];if(size==='fluid'||size==1){}else{setsize=1;width=event.size[0];height=event.size[1];}}
if(rtbdemandunfill!=null){if(setsize==0){var sizes=adslot1.getSizes();var width=1;var height=1;result=findMatchingDimensions(sizes);if(result){width=result.width;height=result.height;}}
if(unfilldivid.includes("oop")||unfilldivid.includes("1x1")||unfilldivid.includes("overlay")||unfilldivid.includes("cover")||unfilldivid.includes("interstitial")||unfilldivid.includes("Interstitial")){width=1;height=1;}
if(width==300&&height==50){width=300;height=100;}
rtbdemandtempunfill={};rtbdemandunfill=rtbdemandunfill.replaceAll('\/','');rtbdemandunfill=rtbdemandunfill.replaceAll('\_','');rtbdemandunfill=rtbdemandunfill.replaceAll('\-','');rtbdemandunfill=rtbdemandunfill.replaceAll('\.','');rtbdemandunfill=rtbdemandunfill.replaceAll('\(','');rtbdemandunfill=rtbdemandunfill.replaceAll('\)','');rtbdemandunfill=rtbdemandunfill.replaceAll('\,','');rtbdemandunfill=rtbdemandunfill.replaceAll('\=','');rtbdemandunfill=rtbdemandunfill.replaceAll('\~','');if(rtbdemandtempunfill.hasOwnProperty(rtbdemandunfill)){delete rtbdemandtempunfill[rtbdemandunfill];}
if(event.isEmpty==true){rtbdemandtempunfill['divid']=rtbdemandunfill;rtbdemandtempunfill['unfill']=true;rtbdemandtempunfill['sizewidth']=width;rtbdemandtempunfill['sizeheight']=height
rtbdemandtempunfill['rtbdemandslotname']=rtbdemandslotname;unfilladunitdata[unfilldivid]=rtbdemandtempunfill;if(setsize==1)unfilladunitdata['slotrender']=1;else unfilladunitdata['slotrender']=0;}
else{rtbdemandtempunfill['divid']=rtbdemandunfill;rtbdemandtempunfill['unfill']=false;rtbdemandtempunfill['sizewidth']=width;rtbdemandtempunfill['sizeheight']=height;rtbdemandtempunfill['rtbdemandslotname']=rtbdemandslotname;unfilladunitdata[unfilldivid]=rtbdemandtempunfill;if(setsize==1)unfilladunitdata['slotrender']=1;else unfilladunitdata['slotrender']=0;}}
try{var slot=event.slot;var vs2=null;var vs2=slot.getSlotElementId();var adunithijack=vs2;if(adunithijack!=undefined){adunithijack=slot.getAdUnitPath();adunithijack=adunithijack.split('/');adunithijack=adunithijack[adunithijack.length-1];if(adunithijack!=null){}}
var childDiv=document.getElementById(vs2);if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"unfilledabm"+unfilledabm+"event.isEmpty"+event.isEmpty+"observehijack[vs2]"+observehijack[vs2]);}
temphijack="";if(event.isEmpty==true&&unfilledabm==1&&vs2&&childDiv!=null&&vs2.indexOf("rtbdemand")<0&&vs2.indexOf("intercode")<0&&observehijack[vs2]==undefined){tempnew=childDiv.outerHTML;tempnew=vs2+tempnew;temphijack=tempnew;var temp_caps=tempnew.toUpperCase();var windowwidth=window.innerWidth;if(windowwidth<=767){var anddevice="MOBILE";}
else{var anddevice="DESKTOP";}
var sessionand=0;size="ALL";var hijackreport1=1;var rtbdemandnewarray={};rtbdemandnewarray['unfilledadunitkey']=1;rtbdemandnewarray['hijackadunitkey']=0;rtbdemandnewarray['view']=0;if(unfilledabm==1&&hijackreport1==1){rtbdemandnewarray['unfilledadunitkey']=1;}
if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"unfilledabm"+unfilledabm+"hijackdone[vs2]"+hijackdone[vs2]+"temphijack"+temphijack);}
if(hijackdone[vs2]==undefined&&temphijack.indexOf("rtbdemand")<0&&((unfilledabm==1)))
firstlookrefreshbid2(vs2,childDiv,rtbdemandnewarray,-1,temp_caps);}
if(vs2){vs3=vs2.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');vs3=vs3.replaceAll('\,','');vs3=vs3.replaceAll('\=','');vs3=vs3.replaceAll('\~','');eval("time_refreshunit"+vs3+" = timer_refresh");if(event.isEmpty==true)
slot_vis[vs3]=100;else
slot_vis[vs3]=0;}
if(vs2&&childDiv!=null&&vs2.indexOf("intercode")<0&&vs2.indexOf("cubextra")<0&&obsrefreshdone[vs2]==undefined){if(getQueryString_val_new("unfilldebug")==1){console.log("vs2"+vs2+"obsrefreshdone[vs2]"+obsrefreshdone[vs2]);}
obsrefreshdone[vs2]=adunithijack;refreshobserver.observe(childDiv);vs3=vs2;vs3=vs3.replaceAll('\/','');vs3=vs3.replaceAll('\_','');vs3=vs3.replaceAll('\-','');vs3=vs3.replaceAll('\.','');vs3=vs3.replaceAll('\(','');vs3=vs3.replaceAll('\)','');vs3=vs3.replaceAll('\,','');vs3=vs3.replaceAll('\=','');vs3=vs3.replaceAll('\~','');if(slot_vis[vs3]==undefined)slot_vis[vs3]=0;if(event.isEmpty==true){slot_vis[vs3]=100;showDivIfHidden(childDiv);}
try{time_refreshunit=eval("time_refreshunit"+vs3);nextactive=eval("active"+vs3);nextpassive=eval("passive"+vs3);nextnumber=eval("nextnumber"+vs3);}
catch(e){nextactive=refresh+rtbdemandtotalSeconds1;nextpassive=timer_refresh+timebased_refresh;time_refreshunit=timer_refresh;nextnumber=0;}
eval("passive"+vs3+" = nextpassive");eval("active"+vs3+" = nextactive");eval("time_refreshunit"+vs3+" = time_refreshunit");eval("nextnumber"+vs3+" = nextnumber");}}
catch(e){console.log('EXCEPTIONsize'+e.stack);}});});}loadGtag("9298809_pv");