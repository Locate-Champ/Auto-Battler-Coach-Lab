(function(){const path=window.location.pathname.replace(/\/+$/,'');if(path==='/patreon'||path==='/team-builder'||path.startsWith('/team-builder/')||path==='/privacy-policy'||path==='/terms-of-service'){return;}
const ADS_DISABLED_KEY='no_ads';const userDisabledAds=!!localStorage.getItem(ADS_DISABLED_KEY);function awaitAdBlockResult(){return new Promise(resolve=>{const TEST_ID='VONvFyELHBzt';let done=false;function finish(blocked){if(done)return;done=true;resolve(blocked);}
const s=document.createElement('script');s.src='/adfx.loader.bind.js';s.async=false;s.onerror=()=>finish(true);s.onload=()=>{setTimeout(()=>{const blocked=!document.getElementById(TEST_ID);finish(blocked);},0);};setTimeout(()=>finish(true),2000);document.head.appendChild(s);});}
function injectNitroScripts(){if(window.nitroAds)return;const inline=document.createElement('script');inline.setAttribute('data-cfasync','false');inline.textContent=`
			window.nitroAds = window.nitroAds || {
				createAd: function () {
					return new Promise(r => {
						window.nitroAds.queue.push(['createAd', arguments, r]);
					});
				},
				addUserToken: function () {
					window.nitroAds.queue.push(['addUserToken', arguments]);
				},
				queue: []
			};
		`;document.head.appendChild(inline);const ext=document.createElement('script');ext.setAttribute('data-cfasync','false');ext.async=true;ext.src='https://s.nitropay.com/ads-2100.js';document.head.appendChild(ext);}
let nitroLoaded=false;function onNitroLoaded(cb){if(window.nitroAds&&window.nitroAds.loaded){nitroLoaded=true;cb();}else{document.addEventListener('nitroAds.loaded',function handler(){document.removeEventListener('nitroAds.loaded',handler);nitroLoaded=true;cb();});}}
function placeAdMarkup(){let inserted=false;let observer=null;function insert(){if(inserted)return;const primary=document.getElementById('primary');if(!primary)return;if(!document.querySelector('.page-top-ads')){const wrap=document.createElement('div');wrap.className='page-top-ads';wrap.innerHTML=`
					<div class="page-top-banner-ad">
						<div id="nitro_page_top_banner"></div>
					</div>
					<div class="page-top-video-ad">
						<div id="nitro_video_ad"></div>
					</div>
				`;primary.insertBefore(wrap,primary.firstChild);}
inserted=true;if(observer)observer.disconnect();if(nitroLoaded)createMarkupAds();}
insert();if(!inserted){observer=new MutationObserver(insert);observer.observe(document.documentElement,{childList:true,subtree:true});setTimeout(()=>observer.disconnect(),10000);}}
function createImmediateAds(isAdBlocked=false){if(!isAdBlocked){window.nitroAds.createAd('nitro_anchor_ad1',{refreshTime:30,format:'anchor-v2',anchor:'bottom',anchorClose:true,anchorPersistClose:false,anchorBgColor:'rgb(10 10 10 / 60%)',mediaQuery:'(min-width: 0px)',report:{enabled:true,icon:true,wording:'Report Ad',position:'top-right'}});}
window.nitroAds.createAd('nitro-sticky-side-ad-left-large',{refreshTime:30,format:'rail',rail:'left',railOffsetTop:0,railOffsetBottom:0,railVerticalAlign:'top',railStickyTop:100,railSpacing:5,railCloseColor:'rgb(255 255 255)',railCollisionWhitelist:['*'],railStack:false,mediaQuery:'(min-width: 1900px)',sizes:[['300','600'],['160','600'],['300','250']],report:{enabled:true,icon:true,wording:'Report Ad',position:'top-right'}});window.nitroAds.createAd('nitro-sticky-side-ad-left-medium',{refreshTime:30,format:'rail',rail:'left',railOffsetTop:0,railOffsetBottom:0,railVerticalAlign:'top',railStickyTop:100,railSpacing:5,railCloseColor:'rgb(255 255 255)',railCollisionWhitelist:['*'],mediaQuery:'(min-width: 1645px) and (max-width: 1899px)',sizes:[['160','600']],report:{enabled:true,icon:true,wording:'Report Ad',position:'top-right'}});if(!path.startsWith('/composition/')){}}
function createMarkupAds(isAdBlocked=false){if(createMarkupAds.done)return;const videoSlot=document.getElementById('nitro_video_ad');const bannerSlot=document.getElementById('nitro_page_top_banner');if(!(videoSlot&&bannerSlot))return;if(isAdBlocked){window.nitroAds.createAd('nitro_page_top_banner',{refreshTime:30,renderVisibleOnly:false,mediaQuery:'(min-width: 1350px)',sizes:[['728','90'],['300','250'],['336','280']],report:{enabled:true,icon:true,wording:'Report Ad',position:'top-right'}});window.nitroAds.createAd('nitro_page_top_banner',{refreshTime:30,renderVisibleOnly:false,mediaQuery:'(min-width: 804px) and (max-width: 1349px)',sizes:[['300','250'],['728','90'],],report:{enabled:true,icon:true,wording:'Report Ad',position:'top-right'}});}else{window.nitroAds.createAd('nitro_video_ad',{format:'video-nc',report:{enabled:true,icon:true,wording:'Report Ad',position:'top-left'},video:{"mobile":"compact",}});}
createMarkupAds.done=true;}
if(userDisabledAds){if(typeof gtag==='function'){gtag('event','ad_opt_out',{event_category:'Blocking Ads',event_label:'LocalStorage Toggle',non_interaction:true});}
return;}
awaitAdBlockResult().then((blocked)=>{if(typeof gtag==='function'){gtag('event','blocking_ads',{event_category:'Blocking Ads',event_label:blocked?'Yes':'No',non_interaction:true});}
placeAdMarkup();injectNitroScripts();onNitroLoaded(()=>{createImmediateAds(blocked);createMarkupAds(blocked);});});})();