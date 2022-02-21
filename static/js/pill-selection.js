       $(".nav.nav-pills.your_nav_class li").on("click",function(){
          $(".nav.nav-pills.your_nav_class li").removeClass("active");
          $(this).addClass("active");
        });