$( function() {
    var AppView = Backbone.View.extend({
        el : $(".content")[0],

        // Delegated events for creating new items, and clearing completed ones.
        events : {
            "click .startCluster" :  "startCluster",
            "click .stopCluster" : "stopCluster"
        },

        // At initialization we bind to the relevant events on the `Todos`
        // collection, when items are added or changed. Kick things off by
        // loading any preexisting todos that might be saved in *localStorage*.
        initialize : function() {
        },

        pollStdout : _.once(function() {
            var inner = _.bind(function() {
                $.ajax( { url : '/readstdout',
                          data : {},
                          success : _.bind(_.partial(function(inner, data) {
                              for(var i = 0; i < data.length; i++)
                              {
                                  var msg = '';
                                  
                                  for(var c in data[i].msg)
                                  {
                                      if(data[i].msg[c] == '\n')
                                      {
                                          if(msg.length > 0)
                                              this.handleMessage({ status : data[i].status, msg : msg });

                                          msg = ''

                                          this.createMessage();
                                      }
                                      else
                                      {
                                          msg += data[i].msg[c];
                                      }
                                  }
                                  
                                  if(msg.length > 0)
                                      this.handleMessage({ status : data[i].status, msg : msg });
                              }
                           
                              setTimeout(_.bind(inner, this), 1000);
                          }, arguments.callee), this),
                          error : _.bind(_.partial(function(inner, data) {
                              setTimeout(_.bind(inner, this), 1000);
                          }, arguments.callee), this),
                          method : 'POST',
                          dataType : 'json'
                        });
            }, this);
            
            inner();
        }),
                            
        startCluster : function() {
            $.post( '/startmolns',
                    {
                        aws_access_key : $( 'input[name=aws_access_key]' ).val(),
                        aws_secret_key : $( 'input[name=aws_secret_key]' ).val(),
                        head_node : $( '.headNode' ).val(),
                        pw : $( 'input[name=password]' ).val()
                    },
                    _.bind(function(data) {
                        this.createMessage(data);
                    }, this),
                    "json"
                  );
        },

        stopCluster : function() {
            $.post( '/stopmolns',
                    {},
                    _.bind(function(data) {
                        this.createMessage(data);
                    }, this),
                    "json"
                  );
        },

        createMessage : function(data) {
            var dateString = '';

            var date = new Date();
            var dateString = date.getHours() + ':' + date.getMinutes() + ':' + date.getSeconds();

            if(typeof data != "undefined")
                this.handleMessage(data);

            var messages = $( '.messages' );

            messages.append( '<div style="display: none;" class="line"><span class="time">' + dateString + '</span>: <pre style="display : inline;" class="content"></pre></div>' );

            if(messages.length)
                messages.scrollTop(messages[0].scrollHeight - messages.height());
        },

        handleMessage : function(data) {
            var line = $( '.messages>div.line' ).last();

            line.show();

            var element = line.find( 'pre.content' );
            var time = line.find( 'span.time' );

            var date = new Date();

            time.text(date.getHours() + ':' + date.getMinutes() + ':' + date.getSeconds());

            if(data.status)
            {
                element.append( '<span><font color="green">' + data.msg + '</font></span>' );
            } else {
                element.append( '<span><font color="red">' + data.msg + '</font></span>' );
            }

            var messages = $( '.messages' );

            if(messages.length)
                messages.scrollTop(messages[0].scrollHeight - messages.height());
        },

        // Re-rendering the App just means refreshing the statistics -- the rest
        // of the app doesn't change.
        render : function() {
            var data = JSON.parse($( '.jsonData' ).text());

            this.$el.find( 'input[name=aws_access_key]' ).val(data['aws_access_key']);
            this.$el.find( 'input[name=aws_secret_key]' ).val(data['aws_secret_key']);

            this.$el.find( '.headNode>option[value="' + data['head_node'] + '"]' ).prop('selected', true);

            $( '.loading' ).hide();

            this.delegateEvents();

            this.createMessage();
            this.pollStdout();

            this.$el.show();
        }
    });

    var App = new AppView();

    App.render();
} );
